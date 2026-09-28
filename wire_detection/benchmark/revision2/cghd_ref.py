#!/usr/bin/env python3
"""Method-independent connectivity reference from the CGHD authors' own annotations.

Inputs per sample (CGHD v12, drafter_*/): the binary stroke map ``segmentation/<stem>.jpg`` and
the labelme instance polygons ``instances/<stem>.json``. No detector, no wire extractor and no
join strategy of ours is used; the only parameters are three morphological tolerances expressed
in units of the per-image median stroke width.

Recipe (it extends CGHD's own ``segmentation.generate_wires``, which fills every symbol polygon
into the stroke map and takes the remaining blobs as wires):

 1. stroke mask S = segmentation <= 127 (the threshold segmentation.py uses).
    stroke width sw = 2 * |S| / |boundary(S)| (area / half-perimeter of thin strokes).
 2. wire mask W = S minus the union of ALL polygons (symbols, text, junctions, crossovers),
    each dilated by d_erase = max(2, round(0.5 sw)) px.
 3. conductors = 8-connected components of W with area >= max(10, 0.5 sw^2).
 4. contact: conductor c touches polygon P iff c has a pixel within d_contact =
    d_erase + max(3, round(sw)) px of P.  Text polygons take no contacts (not conductors,
    not terminals).
 5. junction polygons are conductive nodes: every conductor touching a junction is merged
    through it; a junction also contacts any other polygon directly within d_contact when
    stroke pixels lie in the gap (the stub between them may be fully erased in step 2).
 6. crossover polygons are NOT conductive. The conductor arms entering a crossover (connected
    stroke clusters in its contact band) are paired straight-through: arms whose directions
    from the polygon centre differ by 180 deg +- 45 deg are merged, greedily by deviation.
    Any crossover with an arm count other than 0/1/2/4, or with an arm left unpaired, is
    flagged ``ambiguous_crossover`` (an unpaired arm is left unmerged).
 7. nets: union-find over conductors + junction nodes; a net = the set of non-junction,
    non-crossover, non-text polygons touched by its members. Every symbol (terminal, gnd, vss,
    switch, ...) participates in topology; separate gnd/vss symbols are NOT merged globally
    (the pipeline under test does not do that either). Pin names are 'e' (component level).

Quality flags per image: ambiguous crossovers, electrical symbols in 0 nets (isolated) or in
more nets than terminals (MAX_TERMINALS of build_verified_gt), abutting electrical symbol
pairs (polygons within 2 d_erase with ink between, so no conductor can survive between them),
floating conductors, and nets holding >60% of >=6 electrical symbols. ``clean`` = no ambiguous
crossover, no isolated / over-connected electrical symbol, and >=1 electrical pair.

Output schema matches ground_truth/real_nets_working.json (nets as [[idx,'e'],...] over the
CGHD instance list order, electrical_idxs, components{idx:{type,cx,cy}}, img_wh) plus
provenance + flags.

Run on claw:
  PYTHONPATH=~/circuit-digitization ~/circuit-digitization/.venv/bin/python \
      ~/rev2_scratch_cghd/cghd_ref.py --out ~/rev2_scratch_cghd/out/cghd_ref_nets.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import (  # noqa: E402  (flat import: runs from a scratch copy on claw)
    is_electrical, list_samples, load_shapes, load_stroke_mask, our_type_name)
from wire_detection.benchmark.build_verified_gt import MAX_TERMINALS

PARAMS = dict(erase_k=0.5, erase_min=2, contact_k=1.0, contact_min=3,
              min_area_k=0.5, min_area_min=10, xover_tol_deg=45.0, giant_frac=0.6,
              xover_junction_arms=True, switch_closed=False)
# Recipe history (reported in the benchmark .md): v1 = xover_junction_arms False; v2 (frozen,
# used for every evaluation number) adds junction arms after the validation disagreement
# analysis found crossovers abutting a junction (C66_D2_P4). switch_closed=True is a sensitivity
# variant only (the human nets bridged switches; every join method under test treats a switch
# as a component).
NONCOND = {"text"}


def max_terminals(t: str) -> int:
    """build_verified_gt.MAX_TERMINALS (the rule applied to the human GT) for 2/3-terminal parts;
    relaxed for multi-pin parts, whose drawn pin count varies (8-pin opamps, 40-pin ICs)."""
    if t in ("opamp", "opamp-schmitt"):
        return 8
    if t.startswith("IC"):
        return 64
    return MAX_TERMINALS.get(t, 3)
JUNCTION = "junction"
CROSSOVER = "crossover"


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


CONTAINER_CLASSES = {"transformer", "optocoupler", "relay"}


def find_containers(shapes) -> set[int]:
    """CGHD annotates complex parts twice: an overall polygon (transformer / optocoupler / relay)
    plus its sub-components (inductors, LED + photo-element, coil + switch). Such an overall
    polygon is grouping-only: it is neither erased nor given contacts, so wires reach the
    sub-components. Only applied when >=1 other polygon lies >=50% inside it."""
    out = set()
    for i, s in enumerate(shapes):
        if s["label"] not in CONTAINER_CLASSES:
            continue
        pi = s["points"].astype(np.float32)
        for j, t in enumerate(shapes):
            if j == i or t["label"] in ("text", "junction", "crossover"):
                continue
            inside = [cv2.pointPolygonTest(pi, (float(x), float(y)), False) >= 0 for x, y in t["points"]]
            c = t["points"].mean(axis=0)
            if cv2.pointPolygonTest(pi, (float(c[0]), float(c[1])), False) >= 0 and np.mean(inside) >= 0.5:
                out.add(i)
                break
    return out


def stroke_width(S: np.ndarray) -> float:
    u8 = S.astype(np.uint8)
    er = cv2.erode(u8, np.ones((3, 3), np.uint8))
    boundary = int((u8 & (1 - er)).sum())
    return 2.0 * float(u8.sum()) / max(boundary, 1)


def _disk(r: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def _local_poly_mask(pts, x0, y0, w, h, dil):
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(pts - [x0, y0]).astype(np.int32)], 1)
    return cv2.dilate(m, _disk(dil)) if dil > 0 else m


def build_reference(shapes, S, params=PARAMS):
    H, W = S.shape
    sw = stroke_width(S)
    d_erase = max(params["erase_min"], int(round(params["erase_k"] * sw)))
    d_contact = d_erase + max(params["contact_min"], int(round(params["contact_k"] * sw)))
    min_area = max(params["min_area_min"], params["min_area_k"] * sw * sw)

    containers = find_containers(shapes)
    # 2. wire mask: erase every polygon (dilated) except grouping-only containers
    erase = np.zeros((H, W), np.uint8)
    for ci, s in enumerate(shapes):
        if ci in containers:
            continue
        cv2.fillPoly(erase, [np.round(s["points"]).astype(np.int32)], 1)
    erase = cv2.dilate(erase, _disk(d_erase))
    Wm = (S & (erase == 0)).astype(np.uint8)
    n_lab, lab, stats, _cent = cv2.connectedComponentsWithStats(Wm, connectivity=8)
    keep_lab = np.zeros(n_lab, bool)
    keep_lab[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area

    # 4. contacts polygon -> conductor labels (local windows)
    contacts = []            # per shape: set of conductor labels
    windows = []
    for s in shapes:
        pts = s["points"]
        x0 = max(0, int(math.floor(pts[:, 0].min())) - d_contact - 2)
        y0 = max(0, int(math.floor(pts[:, 1].min())) - d_contact - 2)
        x1 = min(W, int(math.ceil(pts[:, 0].max())) + d_contact + 3)
        y1 = min(H, int(math.ceil(pts[:, 1].max())) + d_contact + 3)
        windows.append((x0, y0, x1, y1))
        if s["label"] in NONCOND or len(windows) - 1 in containers or x1 <= x0 or y1 <= y0:
            contacts.append(set()); continue
        m = _local_poly_mask(pts, x0, y0, x1 - x0, y1 - y0, d_contact)
        ls = np.unique(lab[y0:y1, x0:x1][m > 0])
        contacts.append({int(l) for l in ls if l and keep_lab[l]})

    uf = UF()
    flags = Counter()
    xover_detail = []
    kinds = [s["label"] for s in shapes]
    JL = {JUNCTION} | ({"switch"} if params.get("switch_closed") else set())  # conductive nodes
    sym_idx = [i for i, k in enumerate(kinds)
               if k not in NONCOND and k not in JL and k != CROSSOVER and i not in containers]

    # 5. junctions merge their conductors; direct junction<->polygon contacts across erased stubs
    direct = defaultdict(set)   # junction idx -> symbol idxs / junction idxs touched directly
    for i, k in enumerate(kinds):
        if k not in JL:
            continue
        for l in contacts[i]:
            uf.union(("J", i), ("C", l))
        uf.find(("J", i))
    for i, j in combinations(range(len(shapes)), 2):
        if kinds[i] not in JL and kinds[j] not in JL:
            continue
        if kinds[i] in NONCOND or kinds[j] in NONCOND or CROSSOVER in (kinds[i], kinds[j]):
            continue
        a, b = windows[i], windows[j]
        x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
        if x1 <= x0 or y1 <= y0:
            continue
        mi = _local_poly_mask(shapes[i]["points"], x0, y0, x1 - x0, y1 - y0, d_contact)
        mj = _local_poly_mask(shapes[j]["points"], x0, y0, x1 - x0, y1 - y0, d_contact)
        ov = (mi > 0) & (mj > 0)
        if ov.any() and S[y0:y1, x0:x1][ov].any():
            if kinds[i] in JL and kinds[j] in JL:
                uf.union(("J", i), ("J", j))
            else:
                ji, si = (i, j) if kinds[i] in JL else (j, i)
                direct[ji].add(si)

    # abutting electrical symbols (info flag only: no conductor can survive between them)
    elec = [i for i in sym_idx if is_electrical(kinds[i])]
    gap = 2 * d_erase + 1
    abut = []
    for i, j in combinations(sym_idx, 2):
        if not (is_electrical(kinds[i]) or is_electrical(kinds[j])):
            continue
        a, b = windows[i], windows[j]
        x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
        if x1 <= x0 or y1 <= y0:
            continue
        mi = _local_poly_mask(shapes[i]["points"], x0, y0, x1 - x0, y1 - y0, 0)
        mj = _local_poly_mask(shapes[j]["points"], x0, y0, x1 - x0, y1 - y0, 0)
        if (mi & mj).any():          # overlapping polygons (complex parts) -> not abutting
            continue
        mi = cv2.dilate(mi, _disk(gap)); mj = cv2.dilate(mj, _disk(gap))
        ov = (mi > 0) & (mj > 0)
        if ov.any() and S[y0:y1, x0:x1][ov].any():
            abut.append([i, j])

    # 6. crossovers: straight-through pairing of arms. Arm direction = local wire direction
    #    (centroid of the arm's conductor pixels in the ring d_contact..d_contact+4sw from the
    #    polygon, minus the arm's contact centroid), so hop glyphs with off-centre polygons work.
    tol = params["xover_tol_deg"]
    R = d_contact + int(round(4 * sw)) + 2
    for i, k in enumerate(kinds):
        if k != CROSSOVER:
            continue
        pts = shapes[i]["points"]
        x0 = max(0, int(math.floor(pts[:, 0].min())) - R)
        y0 = max(0, int(math.floor(pts[:, 1].min())) - R)
        x1 = min(W, int(math.ceil(pts[:, 0].max())) + R + 1)
        y1 = min(H, int(math.ceil(pts[:, 1].max())) + R + 1)
        pm = _local_poly_mask(pts, x0, y0, x1 - x0, y1 - y0, 0)
        dist = cv2.distanceTransform((1 - pm).astype(np.uint8), cv2.DIST_L2, 3)
        sub = lab[y0:y1, x0:x1]
        cond = (sub > 0) & keep_lab[sub]
        band = cond & (dist <= d_contact)
        nb, bl, bst, bcent = cv2.connectedComponentsWithStats(band.astype(np.uint8), connectivity=8)
        mo = cv2.moments(pm, binaryImage=True)
        pc = np.array([mo["m10"] / mo["m00"], mo["m01"] / mo["m00"]]) if mo["m00"] else pts.mean(0) - [x0, y0]
        ring = cond & (dist > d_contact) & (dist <= R)
        ry, rx = np.nonzero(ring)
        rl = sub[ry, rx]
        arms = []
        for bb in range(1, nb):
            if bst[bb, cv2.CC_STAT_AREA] < max(3, sw):
                continue
            labs = sub[bl == bb]
            l = int(np.bincount(labs[labs > 0]).argmax())
            c = np.array(bcent[bb])
            sel = (rl == l) & ((rx - c[0]) ** 2 + (ry - c[1]) ** 2 <= (R + d_contact) ** 2)
            v = (np.array([rx[sel].mean(), ry[sel].mean()]) - c) if sel.sum() >= max(3, sw) else (c - pc)
            n = float(np.hypot(*v))
            arms.append((("C", l), v / n if n > 1e-6 else np.array([0.0, 0.0])))
        if params.get("xover_junction_arms", True):
            # v2: a junction abutting the crossover (the stub between them fully erased in step
            # 2) is an arm too, pointing from the crossover centre to the junction centre.
            arm_labels = {a[0][1] for a in arms}
            for j, kj in enumerate(kinds):
                if kj != JUNCTION or contacts[j] & arm_labels:
                    continue
                qj = shapes[j]["points"]
                if (qj[:, 0].max() < x0 or qj[:, 0].min() > x1 or qj[:, 1].max() < y0 or qj[:, 1].min() > y1):
                    continue
                mj = _local_poly_mask(qj, x0, y0, x1 - x0, y1 - y0, d_contact)
                ov = (mj > 0) & (dist <= d_contact)
                if ov.any() and S[y0:y1, x0:x1][ov].any():
                    v = qj.mean(axis=0) - [x0, y0] - pc
                    n = float(np.hypot(*v))
                    arms.append((("J", j), v / n if n > 1e-6 else np.array([0.0, 0.0])))

        def dev(a, b):
            d = float(np.clip(-np.dot(arms[a][1], arms[b][1]), -1, 1))
            return math.degrees(math.acos(d))
        n_arm = len(arms)
        if n_arm == 4:
            matchings = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
            best = min(matchings, key=lambda m: max(dev(*m[0]), dev(*m[1])))
            cand = [(dev(*pr), *pr) for pr in best]
        else:
            cand = sorted((dev(a, b), a, b) for a, b in combinations(range(n_arm), 2))
        used, pairs = set(), []
        for dv, a, b in cand:
            if dv <= tol and a not in used and b not in used:
                used |= {a, b}; pairs.append((a, b, round(dv, 1)))
                uf.union(arms[a][0], arms[b][0])
        amb = n_arm not in (0, 1, 2, 4) or (n_arm in (2, 4) and len(used) != n_arm)
        if amb:
            flags["ambiguous_crossover"] += 1
        xover_detail.append({"idx": i, "arms": n_arm, "paired": len(pairs), "ambiguous": bool(amb),
                             "devs": [p[2] for p in pairs],
                             "all_devs": [round(c[0], 1) for c in cand]})

    # 7. nets
    members = defaultdict(set)
    for i in sym_idx:
        for l in contacts[i]:
            members[uf.find(("C", l))].add(i)
    for ji, syms in direct.items():
        members[uf.find(("J", ji))].update(syms)
    # conductors that touch nothing (info)
    touched = set()
    for i, k in enumerate(kinds):
        if k not in NONCOND:
            touched |= contacts[i]
    kept = [l for l in range(1, n_lab) if keep_lab[l]]
    flags["floating_conductors"] = sum(1 for l in kept if l not in touched)
    # a conductor group touching a single symbol (e.g. a glyph stroke poking out of its own
    # polygon, a dangling stub) carries no connectivity: drop single-member groups.
    nets = sorted(sorted(v) for v in members.values() if len(v) >= 2)

    cnt = Counter()
    for n in nets:
        for i in set(n):
            cnt[i] += 1
    isolated = [i for i in elec if cnt.get(i, 0) == 0]
    over = [i for i in elec if cnt.get(i, 0) > max_terminals(our_type_name(kinds[i]))]
    es = set(elec)
    npairs = len({p for n in nets for p in combinations(sorted(set(n) & es), 2)})
    giant = any(len(set(n) & es) > params["giant_frac"] * len(es) for n in nets) if len(es) >= 6 else False
    clean = (flags["ambiguous_crossover"] == 0 and not isolated and not over and npairs > 0)
    return {
        "nets": nets, "electrical_idxs": elec, "stroke_width": round(sw, 2),
        "d_erase": d_erase, "d_contact": d_contact, "min_area": round(min_area, 1),
        "n_conductors": len(kept),
        "flags": {"ambiguous_crossover": flags["ambiguous_crossover"],
                  "isolated_electrical": isolated, "overconnected_electrical": over,
                  "abutting_electrical_pairs": abut, "floating_conductors": flags["floating_conductors"],
                  "giant_net": bool(giant), "n_crossover": sum(1 for k in kinds if k == CROSSOVER)},
        "crossovers": xover_detail, "containers": sorted(containers), "n_electrical_pairs": npairs, "clean": bool(clean),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--variant", default="v2", choices=["v1", "v2", "v2_switch_closed"])
    args = ap.parse_args()
    params = dict(PARAMS)
    if args.variant == "v1":
        params["xover_junction_arms"] = False
    if args.variant == "v2_switch_closed":
        params["switch_closed"] = True
    out = {"_provenance": {
        "source": "CGHD v12 (Thoma, Bayer et al., DFKI), Zenodo 10056817; instance polygons + binary "
                  "stroke maps. Licence: see caveats (Zenodo record CC BY 4.0; bundled README states "
                  "CC BY-SA 3.0).",
        "method": "wire_detection/benchmark/revision2/cghd_ref.py (stroke map minus symbol polygons; "
                  "conductor CCs; junction merge; crossover straight-through pairing)",
        "params": params, "variant": args.variant, "component_index_space": "order of shapes in instances/<stem>.json "
                  "(polygons with >=3 points)"}}
    samples = list_samples()
    if args.only:
        samples = [s for s in samples if s[1] in set(args.only)]
    if args.limit:
        samples = samples[:args.limit]
    for n, (d, stem) in enumerate(samples):
        shapes, Wj, Hj = load_shapes(d, stem)
        S = load_stroke_mask(d, stem)
        H, W = S.shape   # 2 files carry a wrong labelme imageWidth; the seg map == image size
        r = build_reference(shapes, S, params)
        r["json_size_mismatch"] = (Wj, Hj) != (W, H)
        comps = {}
        for i in r["electrical_idxs"]:
            p = shapes[i]["points"]
            comps[str(i)] = {"type": our_type_name(shapes[i]["label"]),
                             "cx": round(float(p[:, 0].mean()) / W, 4), "cy": round(float(p[:, 1].mean()) / H, 4)}
        out[stem] = {"nets": [[[i, "e"] for i in net] for net in r["nets"]],
                     "n_components": len(shapes), "electrical_idxs": r["electrical_idxs"],
                     "components": comps, "img_wh": [W, H], "drafter": d,
                     "source": "cghd-annotation-derived (cghd_ref.py), not human-verified",
                     **{k: v for k, v in r.items() if k not in ("nets", "electrical_idxs")}}
        f = r["flags"]
        print(f"{n+1:>3} {d:<11}{stem:<13} sw={r['stroke_width']:>5.1f} cond={r['n_conductors']:>3} "
              f"nets={len(r['nets']):>3} elec={len(r['electrical_idxs']):>2} pairs={r['n_electrical_pairs']:>3} "
              f"xamb={f['ambiguous_crossover']} iso={len(f['isolated_electrical'])} "
              f"over={len(f['overconnected_electrical'])} abut={len(f['abutting_electrical_pairs'])} "
              f"clean={r['clean']}", flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    imgs = [v for k, v in out.items() if not k.startswith("_")]
    print(f"wrote {args.out}: {len(imgs)} images, clean {sum(v['clean'] for v in imgs)}")


if __name__ == "__main__":
    main()
