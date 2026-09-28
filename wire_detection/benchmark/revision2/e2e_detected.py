#!/usr/bin/env python3
"""End-to-end join F1 with DETECTED component boxes, detector run on the CGHD ORIGINAL image.

Context (revision 2, R2-2 / R2-4). The earlier end-to-end attempt
(`wire_detection/benchmark/detected_boxes_eval.py`) ran the detector directly on the 704x704
benchmark images. Those images are not what the detector was trained on: `stretch_check.py`
shows each is a non-aspect-preserving (stretch) resize to 704x704 of either the CGHD photo or
its binary segmentation map, in 14/31 cases after a flip/transpose/rotation. This script instead

  1. runs the trained detector on the EXIF-corrected CGHD original at its training imgsz (1024),
  2. maps every OBB vertex into benchmark (704) coordinates with the per-image geometry found by
     `stretch_check.py` (dihedral transform -> per-axis stretch -> small ECC affine refinement),
  3. runs exactly the downstream path of detected_boxes_eval.py: detect_wires on the 704 image
     with the detected components, make_pins, run_strategy("scale_completion"), greedy IoU>=0.3
     matching to the annotated boxes, pair-F1 against ground_truth/real_nets_verified.json.

Arms (all through one scoring function):
  gt_direct            annotated boxes, scored exactly as join_eval_real_f1.py (expect 418/37/66)
  gt_oracle_matching   annotated boxes, shuffled, fed through the detection relabel/IoU-match path
  det704@c             detector on the 704 benchmark image, as detected_boxes_eval.py (current code: 0.504
                       at c=0.5; the committed 0.247 came from the pre-b2e245f class-index table)
  benchorient@c        diagnostic: full-res original flipped/rotated into the benchmark orientation, then
                       only stretch+ECC mapped (isolates orientation from stretch/resolution)
  orig@c               detector on the original, mapped to 704  (the new end-to-end arm)
  decomposition (orig detections, each c):
    B gt_minus_missed        annotated boxes, only those matched by some detection
    C B_plus_spurious        B + unmatched detections (predicted class, detected geometry)
    D det_loc_gt_class       all detections; matched ones relabelled with their GT class
    E = orig@c               all detections, predicted class
  crossover (R2-4):
    F E_fix_crossover        E, but every GT crossover not detected AS crossover is replaced by
                             its annotated box (the matched wrong-class detection is removed)
    G E_drop_det_crossover   E, minus detections that correctly found a GT crossover
  voc_sanity                 CGHD VOC boxes mapped through the same geometry, IoU vs annotated boxes

Run on claw:
  cd ~/rev2_scratch/e2e && PYTHONPATH=~/circuit-digitization:. /home/claw/venv-ml/bin/python \
      e2e_detected.py --repo ~/circuit-digitization --out e2e_detected_n31.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import time
import xml.etree.ElementTree as ET
from itertools import combinations
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from stretch_check import DIHEDRAL, corr, find_original, find_seg, psnr

GT_IMAGES = Path(os.environ.get("WIRE_GT_IMAGES", "/home/claw/workspace/ground_truth/labels_few_annot/images"))
CGHD = Path(os.environ.get("CGHD_ORIG", str(Path.home() / "cghd_orig/cghd")))
MODEL_REL = "models/component_detection/yolo26m_obb_16class_aug.pt"
CONFS = [0.25, 0.35, 0.5]
IOU_THRESH = 0.3
STRATEGY = "scale_completion"
SEED = 20260928
CROSSOVER = 5


# ── geometry: original (EXIF-corrected) coords -> benchmark coords ──────────────────────────
def dihedral_point(name, x, y, W, H):
    """Map a point under the same array ops as stretch_check.DIHEDRAL. Returns (x', y', W', H')."""
    if name == "id":
        return x, y, W, H
    if name == "fliplr":
        return W - x, y, W, H
    if name == "flipud":
        return x, H - y, W, H
    if name == "rot180":
        return W - x, H - y, W, H
    if name == "transpose":
        return y, x, H, W
    if name == "rot90cw":       # np.rot90(a, -1)
        return H - y, x, H, W
    if name == "rot90ccw":      # np.rot90(a, 1)
        return y, W - x, H, W
    if name == "antitranspose":  # np.rot90(a, 2).T
        return H - y, W - x, H, W
    raise KeyError(name)


def dihedral_img(name, a):
    """DIHEDRAL for HxWxC arrays (a.T would also move the channel axis)."""
    if name == "transpose":
        return np.ascontiguousarray(a.swapaxes(0, 1))
    if name == "antitranspose":
        return np.ascontiguousarray(np.rot90(a, 2).swapaxes(0, 1))
    return np.ascontiguousarray(DIHEDRAL[name](a))


def _prep(a):
    a = 255.0 - a.astype(np.float32)
    return cv2.GaussianBlur(a, (0, 0), 3)


def fit_geometry(stem):
    bench = cv2.imread(str(GT_IMAGES / f"{stem}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    bh, bw = bench.shape
    op = find_original(stem)
    orig = np.array(ImageOps.exif_transpose(Image.open(op)).convert("L"))
    H, W = orig.shape
    cands = {"image": orig}
    sp = find_seg(stem)
    if sp is not None:
        cands["seg"] = np.array(ImageOps.exif_transpose(Image.open(sp)).convert("L"))
    best = None
    for src, a in cands.items():
        for t, fn in DIHEDRAL.items():
            r = cv2.resize(np.ascontiguousarray(fn(a)), (bw, bh), interpolation=cv2.INTER_AREA)
            c = corr(r, bench)
            if best is None or c > best[0]:
                best = (c, src, t, r)
    c0, src, t, stretched = best
    # ECC affine refinement: warp maps bench coords -> stretched-source coords
    warp = np.eye(2, 3, dtype=np.float32)
    ecc_ok = False
    try:
        _cc, warp = cv2.findTransformECC(_prep(bench), _prep(stretched), warp, cv2.MOTION_AFFINE,
                                         (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), None, 5)
        ecc_ok = True
    except cv2.error:
        warp = np.eye(2, 3, dtype=np.float32)
    aligned = cv2.warpAffine(stretched, warp, (bw, bh), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                             borderValue=255)
    c1 = corr(aligned, bench)
    if not ecc_ok or c1 < c0:
        warp = np.eye(2, 3, dtype=np.float32); c1 = c0
    Minv = cv2.invertAffineTransform(warp)   # stretched-source coords -> bench coords
    return {"stem": stem, "orig_path": str(op), "W": W, "H": H, "bench_w": bw, "bench_h": bh,
            "source": src, "transform": t, "corr_stretch": round(c0, 4), "corr_aligned": round(c1, 4),
            "psnr_aligned": round(psnr(cv2.warpAffine(stretched, warp, (bw, bh),
                                                      flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                                      borderValue=255), bench), 2),
            "ecc_used": bool(ecc_ok and c1 > c0), "Minv": Minv.tolist()}


def map_point(g, x, y, pre_oriented=False):
    """pre_oriented=True: (x, y) is already in the dihedral-transformed full-res frame."""
    if pre_oriented:
        W1, H1 = (g["H"], g["W"]) if g["transform"] in ("transpose", "rot90cw", "rot90ccw", "antitranspose") \
            else (g["W"], g["H"])
        x1, y1 = x, y
    else:
        x1, y1, W1, H1 = dihedral_point(g["transform"], x, y, g["W"], g["H"])
    x2, y2 = x1 * g["bench_w"] / W1, y1 * g["bench_h"] / H1
    M = np.array(g["Minv"])
    return float(M[0, 0] * x2 + M[0, 1] * y2 + M[0, 2]), float(M[1, 0] * x2 + M[1, 1] * y2 + M[1, 2])


# ── detection ───────────────────────────────────────────────────────────────────────────────
def run_detector(model, img, imgsz=None):
    kw = {"task": "obb", "conf": min(CONFS), "verbose": False}
    if imgsz:
        kw["imgsz"] = imgsz
    out = []
    for res in model(img, **kw):
        if res.obb is None:
            continue
        for i in range(len(res.obb.cls)):
            out.append({"cls": int(res.obb.cls[i]), "conf": float(res.obb.conf[i]),
                        "poly": [[float(p[0]), float(p[1])] for p in res.obb.xyxyxyxy[i].tolist()]})
    return out


def to_comps(dets, conf, cls_map, mapper=None, bw=704, bh=704):
    """-> [(gt_scheme_cls, [4 int verts], (x1,y1,x2,y2))], same int casting as detected_boxes_eval."""
    comps = []
    for d in dets:
        if d["conf"] < conf:
            continue
        pts = [mapper(x, y) if mapper else (x, y) for x, y in d["poly"]]
        poly = [(int(x), int(y)) for x, y in pts]
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        comps.append((cls_map.get(d["cls"], 51), poly, bbox, d["conf"]))
    return comps


# ── scoring (worker side) ───────────────────────────────────────────────────────────────────
def _worker_init(repo):
    os.chdir(repo)


def score_arm(task):
    """task: (img_id, arm, comps[(cls, poly, bbox)], labels[list], gt_nets, gt_keep)."""
    from wire_detection.benchmark.build_net_gt import electrical_indices
    from wire_detection.benchmark.join_eval_134 import detect_wires
    from wire_detection.benchmark.join_eval_real_f1 import gt_pairs, prf
    from wire_detection.core.join_strategies import make_pins, make_pins_junction_aware, run_strategy

    img_id, arm, comps, labels, nets, gt_keep = task
    name = img_id.replace("_jpg", "")
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    comps = [(int(c[0]), [tuple(p) for p in c[1]], tuple(c[2])) for c in comps]
    keep = set(electrical_indices(comps))
    gtp = gt_pairs(nets, set(gt_keep))
    wires = detect_wires(gray, comps)
    std_pins = make_pins(wires, comps)
    junc_pins = make_pins_junction_aware(wires, comps)
    _pins, nl = run_strategy(STRATEGY, wires, comps, std_pins=std_pins, junc_pins=junc_pins)
    by_node = {}
    for (ci, _pin), nid in nl.pin_to_node.items():
        if ci in keep:
            by_node.setdefault(nid, set()).add(labels[ci])
    pred = set()
    for s in by_node.values():
        for a, b in combinations(sorted(s, key=str), 2):
            if isinstance(a, int) and isinstance(b, int):
                pred.add(tuple(sorted((a, b))))
            else:
                pred.add((a, b))
    p, r, f1 = prf(gtp, pred)
    tp = len(gtp & pred); fp = len(pred - gtp); fn = len(gtp - pred)
    return img_id, arm, {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": r, "f1": f1,
                         "n_comps": len(comps), "n_elec": len(keep), "wires": len(wires),
                         "fp_pairs": sorted([list(map(str, x)) for x in pred - gtp]),
                         "fn_pairs": sorted([list(x) for x in gtp - pred])}


# ── matching ────────────────────────────────────────────────────────────────────────────────
def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]); ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def match(det, gt, thr=IOU_THRESH):
    """Greedy max-IoU, identical to detected_boxes_eval.match_detections_to_gt. det_idx->(gt_idx, iou)."""
    pairs = sorted(((iou(d[2], g[2]), di, gi) for di, d in enumerate(det) for gi, g in enumerate(gt)
                    if iou(d[2], g[2]) >= thr), reverse=True)
    ud, ug, m = set(), set(), {}
    for v, di, gi in pairs:
        if di in ud or gi in ug:
            continue
        ud.add(di); ug.add(gi); m[di] = (gi, v)
    return m


def micro(rows):
    TP = sum(r["tp"] for r in rows); FP = sum(r["fp"] for r in rows); FN = sum(r["fn"] for r in rows)
    P = TP / (TP + FP) if TP + FP else 1.0
    R = TP / (TP + FN) if TP + FN else 1.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    return {"f1": F, "p": P, "r": R, "tp": TP, "fp": FP, "fn": FN}


def micro_arr(tp, fp, fn):
    d = 2 * tp + fp + fn
    return np.where(d > 0, 2 * tp / np.maximum(d, 1), 1.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=str(Path.home() / "circuit-digitization"))
    ap.add_argument("--out", default="e2e_detected_n31.json")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--B", type=int, default=10000)
    args = ap.parse_args()
    repo = Path(args.repo).expanduser()
    os.chdir(repo)

    from ultralytics import YOLO
    from wire_detection.benchmark.build_net_gt import electrical_indices, find_hdc_label, parse_components
    from wire_detection.benchmark.detected_boxes_eval import MODEL_CLASS_NAME_TO_GT_CLASS
    from wire_detection.core.component_classes import COMPONENT_TYPES, PREFIX_MAP

    gt_all = json.load(open(repo / "ground_truth/real_nets_verified.json"))
    model = YOLO(str(repo / MODEL_REL))
    cls_map = {int(i): MODEL_CLASS_NAME_TO_GT_CLASS.get(str(n).strip().lower(), 51) for i, n in model.names.items()}
    model_overrides = {k: v for k, v in getattr(model, "overrides", {}).items()}
    train_imgsz = int(json.load(open(repo / "models/component_detection/training_config.json"))["config"]["imgsz"])
    prefix = lambda c: PREFIX_MAP.get(COMPONENT_TYPES.get(int(c), ""), "?")

    t0 = time.time()
    rng = random.Random(SEED)
    per_image = {}
    tasks = []
    label_checks = {"committed_equals_find_hdc_label": 0, "mismatch": [], "elec_idx_equal": 0}
    for img_id, entry in gt_all.items():
        stem = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{stem}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        h, w = gray.shape
        committed = (repo / "ground_truth/component_labels" / f"{stem}_jpg.txt").read_text()
        hdc = find_hdc_label(stem)
        if hdc is not None and hdc.read_text().split() == committed.split():
            label_checks["committed_equals_find_hdc_label"] += 1
        else:
            label_checks["mismatch"].append(stem)
        gt = parse_components(committed, w, h)
        gt_keep = list(entry["electrical_idxs"])
        if sorted(electrical_indices(gt)) == sorted(gt_keep):
            label_checks["elec_idx_equal"] += 1
        nets = entry["nets"]
        rec = {"n_gt": len(gt), "n_gt_elec": len(gt_keep)}

        # geometry + detections
        g = fit_geometry(stem)
        rec["geometry"] = {k: v for k, v in g.items() if k != "Minv"} | {"Minv": g["Minv"]}
        orig_bgr = cv2.cvtColor(np.array(ImageOps.exif_transpose(Image.open(g["orig_path"])).convert("RGB")),
                                cv2.COLOR_RGB2BGR)
        det_orig = run_detector(model, orig_bgr, imgsz=train_imgsz)
        # diagnostic: same full-res original, but flipped/rotated into the benchmark orientation
        det_bo = run_detector(model, dihedral_img(g["transform"], orig_bgr), imgsz=train_imgsz)
        det_704 = run_detector(model, str(GT_IMAGES / f"{stem}_jpg.jpg"))   # as detected_boxes_eval (path, default imgsz)
        rec["raw_dets"] = {"orig": len(det_orig), "d704": len(det_704), "benchorient": len(det_bo)}

        # VOC sanity: map CGHD's own boxes through the geometry
        voc = glob.glob(str(CGHD / "drafter_*" / "annotations" / f"{stem}.xml"))
        if voc:
            root = ET.parse(voc[0]).getroot()
            vw = int(root.find("size/width").text); vh = int(root.find("size/height").text)
            vb = []
            for o in root.findall("object"):
                if o.find("name").text == "text":
                    pass
                bb = o.find("bndbox")
                x1, y1, x2, y2 = (float(bb.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
                pts = [map_point(g, x, y) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                vb.append((0, [], (min(xs), min(ys), max(xs), max(ys))))
            m = match(vb, gt, 0.1)
            ious = [v for _gi, v in m.values()]
            rec["voc_sanity"] = {"voc_wh": [vw, vh], "orig_wh": [g["W"], g["H"]], "n_voc": len(vb), "n_gt": len(gt),
                                 "matched": len(m), "median_iou": float(np.median(ious)) if ious else 0.0,
                                 "frac_iou_ge_0.5": float(np.mean([v >= 0.5 for v in ious])) if ious else 0.0}

        gtc = [(c[0], c[1], c[2]) for c in gt]
        # arms with GT boxes
        tasks.append((img_id, "gt_direct", gtc, list(range(len(gt))), nets, gt_keep))
        perm = list(range(len(gt))); rng.shuffle(perm)
        shuffled = [gtc[i] for i in perm]
        mo = match(shuffled, gtc)
        labels = [mo[di][0] if di in mo else f"unmatched_{stem}_{di}" for di in range(len(shuffled))]
        tasks.append((img_id, "gt_oracle_matching", shuffled, labels, nets, gt_keep))
        mo = match(gtc, gtc)
        labels = [mo[di][0] if di in mo else f"unmatched_{stem}_{di}" for di in range(len(gtc))]
        tasks.append((img_id, "gt_oracle_matching_identity_order", gtc, labels, nets, gt_keep))

        mapper = lambda x, y, g=g: map_point(g, x, y)
        mapper_bo = lambda x, y, g=g: map_point(g, x, y, pre_oriented=True)
        rec["conf"] = {}
        for c in CONFS:
            for src, dets, mp in (("orig", det_orig, mapper), ("det704", det_704, None),
                                  ("benchorient", det_bo, mapper_bo)):
                comps = to_comps(dets, c, cls_map, mp)
                dc = [(x[0], x[1], x[2]) for x in comps]
                m = match(dc, gtc)
                labels = [m[di][0] if di in m else f"unmatched_{stem}_{di}" for di in range(len(dc))]
                dkeep = set(electrical_indices(dc))
                gk = set(gt_keep)
                # detection quality, electrical subset
                ag = sum(1 for di, (gi, _v) in m.items() if di in dkeep and gi in gk)
                aw = sum(1 for di, (gi, _v) in m.items() if di in dkeep and gi in gk
                         and prefix(dc[di][0]) == prefix(gtc[gi][0]))
                # recall-side: GT electrical matched by ANY detection (any class)
                gt_hit_any = sum(1 for di, (gi, _v) in m.items() if gi in gk)
                xo_gt = [gi for gi, x in enumerate(gtc) if x[0] == CROSSOVER]
                inv = {gi: di for di, (gi, _v) in m.items()}
                xo_ok = [gi for gi in xo_gt if gi in inv and dc[inv[gi]][0] == CROSSOVER]
                xo_miscls = [gi for gi in xo_gt if gi in inv and dc[inv[gi]][0] != CROSSOVER]
                xo_miss = [gi for gi in xo_gt if gi not in inv]
                xo_fp_det = [di for di, x in enumerate(dc) if x[0] == CROSSOVER and (di not in m or gtc[m[di][0]][0] != CROSSOVER)]
                rec["conf"].setdefault(str(c), {})[src] = {
                    "n_det": len(dc), "n_det_elec": len(dkeep), "elec_match_agnostic": ag, "elec_match_aware": aw,
                    "gt_elec_hit_any": gt_hit_any,
                    "crossover": {"gt": len(xo_gt), "detected_as_crossover": len(xo_ok), "misclassified": len(xo_miscls),
                                  "missed": len(xo_miss), "false_crossover_dets": len(xo_fp_det),
                                  "misclassified_as": [COMPONENT_TYPES.get(int(dc[inv[gi]][0]), "?") for gi in xo_miscls]},
                    "dets": [{"cls": x[0], "conf": round(x[3], 3), "bbox": list(x[2]),
                              "gt": (m[di][0] if di in m else None), "iou": (round(m[di][1], 3) if di in m else None)}
                             for di, x in enumerate(comps)],
                }
                arm = f"{src}@{c}"
                tasks.append((img_id, arm, dc, labels, nets, gt_keep))
                if src == "det704":
                    continue
                pf = "" if src == "orig" else f"{src}:"
                matched_gt = {gi for gi, _v in m.values()}
                # B: GT boxes that some detection found (B_elec / B_nonelec: drop only one kind of miss)
                B_idx = [gi for gi in range(len(gtc)) if gi in matched_gt]
                tasks.append((img_id, f"{pf}B_gt_minus_missed@{c}", [gtc[i] for i in B_idx], B_idx, nets, gt_keep))
                for tag, cond in (("B_elec_missed_only", lambda gi: gi in gk), ("B_nonelec_missed_only", lambda gi: gi not in gk)):
                    idx_ = [gi for gi in range(len(gtc)) if gi in matched_gt or not cond(gi)]
                    tasks.append((img_id, f"{pf}{tag}@{c}", [gtc[i] for i in idx_], idx_, nets, gt_keep))
                # C: B + unmatched detections
                un = [di for di in range(len(dc)) if di not in m]
                tasks.append((img_id, f"{pf}C_plus_spurious@{c}", [gtc[i] for i in B_idx] + [dc[d] for d in un],
                              B_idx + [labels[d] for d in un], nets, gt_keep))
                # D: detected geometry, GT class for matched
                Dc = [(gtc[m[di][0]][0] if di in m else x[0], x[1], x[2]) for di, x in enumerate(dc)]
                tasks.append((img_id, f"{pf}D_det_loc_gt_class@{c}", Dc, labels, nets, gt_keep))
                # F: fix crossovers not detected as crossover
                bad = set(xo_miscls) | set(xo_miss)
                drop = {inv[gi] for gi in xo_miscls}
                Fk = [di for di in range(len(dc)) if di not in drop]
                tasks.append((img_id, f"{pf}F_fix_crossover@{c}", [dc[d] for d in Fk] + [gtc[gi] for gi in sorted(bad)],
                              [labels[d] for d in Fk] + sorted(bad), nets, gt_keep))
                # G: drop correctly-detected crossovers
                dropG = {inv[gi] for gi in xo_ok}
                Gk = [di for di in range(len(dc)) if di not in dropG]
                tasks.append((img_id, f"{pf}G_drop_det_crossover@{c}", [dc[d] for d in Gk], [labels[d] for d in Gk],
                              nets, gt_keep))
        per_image[img_id] = rec
        print(f"  {stem}: {g['source']}/{g['transform']} corr {g['corr_stretch']}->{g['corr_aligned']} "
              f"dets orig={len(det_orig)} 704={len(det_704)} voc_iou={rec.get('voc_sanity', {}).get('median_iou')}",
              flush=True)
    t_det = time.time() - t0
    del model

    print(f"scoring {len(tasks)} arm-image tasks ...", flush=True)
    with Pool(args.workers, initializer=_worker_init, initargs=(str(repo),)) as pool:
        results = pool.map(score_arm, tasks, chunksize=2)
    for img_id, arm, r in results:
        per_image[img_id].setdefault("arms", {})[arm] = r

    ids = list(per_image)
    arms = sorted({a for _i, a, _r in results})
    summary = {}
    cnt = {a: np.array([[per_image[i]["arms"][a][k] for k in ("tp", "fp", "fn")] for i in ids]) for a in arms}
    brng = np.random.default_rng(SEED)
    idx = brng.integers(0, len(ids), size=(args.B, len(ids)))
    base = cnt["gt_direct"]
    bs_base = micro_arr(*(base[idx].sum(1).T))
    for a in arms:
        rows = [per_image[i]["arms"][a] for i in ids]
        mi = micro(rows)
        bs = micro_arr(*(cnt[a][idx].sum(1).T))
        diff = bs - bs_base
        summary[a] = mi | {
            "macro_f1": float(np.mean([r["f1"] for r in rows])),
            "micro_f1_ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
            "diff_vs_gt": mi["f1"] - micro(rows_gt := [per_image[i]["arms"]["gt_direct"] for i in ids])["f1"],
            "diff_vs_gt_ci95": [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))],
        }

    det_quality = {}
    for c in CONFS:
        for src in ("orig", "det704", "benchorient"):
            q = [per_image[i]["conf"][str(c)][src] for i in ids]
            ngt = sum(per_image[i]["n_gt_elec"] for i in ids)
            nd = sum(x["n_det_elec"] for x in q)
            out = {"gt_elec": ngt, "det_elec": nd}
            for kind, key in (("agnostic", "elec_match_agnostic"), ("aware", "elec_match_aware")):
                tp = sum(x[key] for x in q)
                P = tp / nd if nd else 0.0; R = tp / ngt if ngt else 0.0
                out[kind] = {"tp": tp, "p": P, "r": R, "f1": 2 * P * R / (P + R) if P + R else 0.0}
            out["gt_elec_localized_any_class"] = sum(x["gt_elec_hit_any"] for x in q)
            xo = {k: sum(x["crossover"][k] for x in q) for k in
                  ("gt", "detected_as_crossover", "misclassified", "missed", "false_crossover_dets")}
            out["crossover"] = xo
            det_quality[f"{src}@{c}"] = out

    geom = {i: per_image[i]["geometry"] for i in ids}
    voc = [per_image[i]["voc_sanity"] for i in ids if "voc_sanity" in per_image[i]]
    payload = {
        "config": {"strategy": STRATEGY, "iou_match_thresh": IOU_THRESH, "confs": CONFS, "seed": SEED,
                   "bootstrap_B": args.B, "bootstrap": "paired image-level resampling, same indices for all arms",
                   "model": MODEL_REL, "train_imgsz": train_imgsz, "model_overrides_ckpt": {k: str(v) for k, v in model_overrides.items()},
                   "orig_arm": "detector on EXIF-corrected original (BGR array) at imgsz=train_imgsz; OBB vertices mapped "
                               "dihedral->per-axis stretch->ECC affine into 704 space; int-cast like detected_boxes_eval",
                   "det704_arm": "detector on 704 benchmark JPEG path with checkpoint default imgsz (as detected_boxes_eval)",
                   "gt_labels": "ground_truth/component_labels/<stem>_jpg.txt parsed at 704",
                   "conf_filtering": "one inference at conf=min(confs), then filtered; lower-conf boxes cannot suppress "
                                     "higher-conf boxes in NMS so this equals separate runs (up to max_det)"},
        "label_checks": label_checks,
        "summary": summary,
        "detection_quality_electrical": det_quality,
        "geometry_summary": {
            "sources": {s: sum(1 for g in geom.values() if g["source"] == s) for s in ("image", "seg")},
            "transforms": {t: sum(1 for g in geom.values() if g["transform"] == t) for t in DIHEDRAL},
            "corr_aligned_min": min(g["corr_aligned"] for g in geom.values()),
            "corr_aligned_median": float(np.median([g["corr_aligned"] for g in geom.values()])),
            "ecc_used": sum(1 for g in geom.values() if g["ecc_used"]),
        },
        "voc_sanity_summary": {"n_images": len(voc), "median_of_median_iou": float(np.median([v["median_iou"] for v in voc])),
                               "min_median_iou": float(min(v["median_iou"] for v in voc)),
                               "voc_boxes": sum(v["n_voc"] for v in voc), "gt_boxes": sum(v["n_gt"] for v in voc),
                               "matched": sum(v["matched"] for v in voc)},
        "runtime_sec": {"detection_geometry": t_det, "total": time.time() - t0},
        "per_image": per_image,
    }
    json.dump(payload, open(args.out, "w"), indent=1, default=str)
    print(f"\n{'arm':<28}{'microF1':>8}{'P':>7}{'R':>7}{'TP/FP/FN':>13}{'macro':>7}  CI95            dCI95")
    for a in arms:
        s = summary[a]
        print(f"{a:<28}{s['f1']:>8.3f}{s['p']:>7.3f}{s['r']:>7.3f}{s['tp']:>5}/{s['fp']}/{s['fn']:<5}{s['macro_f1']:>7.3f}"
              f"  [{s['micro_f1_ci95'][0]:.3f},{s['micro_f1_ci95'][1]:.3f}]  [{s['diff_vs_gt_ci95'][0]:+.3f},{s['diff_vs_gt_ci95'][1]:+.3f}]")
    print(json.dumps(det_quality, indent=1))
    print(json.dumps(payload["geometry_summary"]), json.dumps(payload["voc_sanity_summary"]), json.dumps(label_checks))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
