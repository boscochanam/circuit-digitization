#!/usr/bin/env python3
"""Bootstrap real net-level ground truth from human-traced GT wires.

The 134-image CGHD subset has GT *wire* labels and GT *component* labels but no
net-level connectivity. This builds proposal net-GT by running a NEUTRAL base
endpoint-graph join (graph_full, NOT the degree_budget strategy under test) over the
PERFECT human-traced GT wires -- on clean perfect wires the topology is recovered
directly. Each image gets an overlay PNG for HUMAN VERIFICATION; the corrected result
is frozen to ground_truth/real_nets.json and used to score both the real join table
(join_eval_real_f1.py) and the real VLM run (vlm_connectivity_eval.py --real).

Circularity note: GT is derived from PERFECT wires with a base join (no completion) and
human-checked; the evaluations score strategies on DETECTED (noisy) wires against it, so
there is no trivial self-evaluation.

Run on claw:
  ./.venv/bin/python -m wire_detection.benchmark.build_net_gt --n 25 \
      --out ground_truth/real_nets.json --overlays output/net_gt_overlays
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from wire_detection.core.component_classes import (
    COMPONENT_TYPES,
    PREFIX_MAP,
    SIMULATABLE_PREFIXES,
)
from wire_detection.core.join_strategies import make_pins, make_pins_junction_aware, run_strategy
from wire_detection.paths import gt_images_dir, gt_labels_dir, hdc_root


def electrical_indices(components: list) -> list[int]:
    """Indices of SPICE-active components (R/C/L/V/D/Q/U) -- text/junction/terminal/gnd
    are excluded so the connectivity metric counts only real circuit elements. Wires from
    ALL components still build the net topology; this only filters which pairs are scored."""
    out = []
    for i, (cls, _verts, _bbox) in enumerate(components):
        tname = COMPONENT_TYPES.get(int(cls), "")
        if PREFIX_MAP.get(tname) in SIMULATABLE_PREFIXES:
            out.append(i)
    return out

# GT paths resolve lazily (at call time, not import time), so importing this module never
# requires the CGHD scans. WIRE_GT_IMAGES / WIRE_GT_WIRE_LABELS / WIRE_HDC_BASE are read
# inside wire_detection.paths.
_gt_images = gt_images_dir
_gt_wire_labels = gt_labels_dir
_hdc_base = hdc_root

HDC_SPLITS = ["train", "valid", "test"]

# force-include showcase circuits (good complexity spread, verified clean detection)
SHOWCASE = ["C84_D2_P1", "C29_D2_P4", "C34_D1_P1", "C63_D2_P3"]

# strategy used to PROPOSE nets from perfect wires. graph_scale is the most conservative
# endpoint-graph join: scale-relative tolerances + directional pin binding + T-junctions,
# but NO 12px end-extension, NO dead-end rescue, NO b-matching completion -- those add
# reach that bridges genuinely-separate nets on clean perfect wires (graph_full over-merged
# small circuits into a single node). Override with --strategy.
GT_STRATEGY = "graph_scale"

_NET_COLORS = [
    (230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180),
    (70, 240, 240), (240, 50, 230), (210, 245, 60), (250, 190, 190), (0, 128, 128),
    (170, 110, 40), (128, 0, 0), (0, 0, 128), (128, 128, 0), (255, 215, 0),
]


def find_hdc_label(image_name: str) -> Path | None:
    """Return the roboflow OBB component label for *image_name*.

    Roboflow exports MULTIPLE augmented copies per source image (rotated / flipped /
    shifted), each as `<name>.rf.<hash>.txt` with a matching `<name>.rf.<hash>.jpg`.
    Picking an arbitrary copy yields labels for a *transformed* image, so the component
    boxes are misaligned with the original GT image. We must select the IDENTITY copy:
    the one whose exported image matches the GT image. Falls back to the first match if no
    image comparison is possible (single copy / missing images)."""
    cands = []  # (split, label_path, ext)
    hdc_base = _hdc_base()
    for split in HDC_SPLITS:
        label_dir = hdc_base / split / "labels"
        for ext in ("_jpg", "_png", "_jpeg"):
            cands += [(split, f, ext) for f in sorted(label_dir.glob(f"{image_name}{ext}.rf.*.txt"))]
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0][1]
    gt = cv2.imread(str(_gt_images() / f"{image_name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    if gt is None:
        return cands[0][1]
    best, bestd = cands[0][1], 1e18
    for split, f, ext in cands:
        h = f.name.split(".rf.")[1].rsplit(".txt", 1)[0]
        rip = hdc_base / split / "images" / f"{image_name}{ext}.rf.{h}.jpg"
        ri = cv2.imread(str(rip), cv2.IMREAD_GRAYSCALE)
        if ri is None or ri.shape != gt.shape:
            continue
        d = float(np.abs(ri.astype("int16") - gt.astype("int16")).mean())
        if d < bestd:
            best, bestd = f, d
    return best


def parse_components(text: str, w: int, h: int) -> list:
    """YOLO-OBB component labels -> [(cls, [4 verts], (x1,y1,x2,y2))]."""
    comps = []
    for line in text.splitlines():
        p = line.split()
        if len(p) != 9:
            continue
        try:
            cls = int(p[0])
            c = [float(x) for x in p[1:9]]
        except ValueError:
            continue
        xs = [int(c[i] * w) for i in range(0, 8, 2)]
        ys = [int(c[i] * h) for i in range(1, 8, 2)]
        comps.append((cls, [(xs[i], ys[i]) for i in range(4)], (min(xs), min(ys), max(xs), max(ys))))
    return comps


def parse_gt_wires(text: str, w: int, h: int) -> list:
    """YOLO-OBB wire labels -> [((x1,y1),(x2,y2))] via short-edge midpoints (centerline)."""
    wires = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 9:
            continue
        try:
            coords = [float(x) for x in parts[1:9]]
        except ValueError:
            continue
        poly = np.array([[int(coords[i] * w), int(coords[i + 1] * h)] for i in range(0, 8, 2)],
                        dtype=np.int32)
        edges = [(i, (i + 1) % 4) for i in range(4)]
        el = sorted((float(np.linalg.norm(poly[a] - poly[b])), a, b) for a, b in edges)
        (_, a1, b1), (_, a2, b2) = el[0], el[1]
        m1 = (poly[a1] + poly[b1]) / 2
        m2 = (poly[a2] + poly[b2]) / 2
        wires.append(((int(m1[0]), int(m1[1])), (int(m2[0]), int(m2[1]))))
    return wires


def netlist_to_nets(netlist) -> list[list[list]]:
    """Group pin_to_node {(ci, pin_name): node} into nets [[ [ci, pin_name], ...], ...]."""
    by_node: dict[int, list[list]] = defaultdict(list)
    for (ci, pin), nid in netlist.pin_to_node.items():
        by_node[nid].append([int(ci), pin])
    return [pins for pins in by_node.values()]


def discover() -> list[str]:
    """All image stems (no _jpg suffix) that have BOTH GT wires and HDC components."""
    out = []
    for gt_file in sorted(_gt_wire_labels().glob("*_jpg.txt")):
        name = gt_file.stem.replace("_jpg", "")
        if not (_gt_images() / f"{name}_jpg.jpg").exists():
            continue
        if find_hdc_label(name) is None:
            continue
        out.append(name)
    return out


def select(names: list[str], n: int) -> list[str]:
    """Force-include showcase, then spread the rest by component count to span complexity."""
    counts = {}
    for name in names:
        hdc = find_hdc_label(name)
        img = cv2.imread(str(_gt_images() / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        if img is None or hdc is None:
            continue
        h, w = img.shape
        counts[name] = len(parse_components(hdc.read_text(), w, h))
    ranked = sorted(counts, key=lambda k: counts[k])
    chosen = [s for s in SHOWCASE if s in counts]
    remaining = [r for r in ranked if r not in chosen]
    if remaining and len(chosen) < n:
        step = max(1, len(remaining) // (n - len(chosen)))
        chosen += remaining[::step][: n - len(chosen)]
    return chosen[:n]


def draw_overlay(gray, components, wires, nets, out_path: Path) -> None:
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for (a, b) in wires:
        cv2.line(img, a, b, (160, 160, 160), 2)
    for i, (_cls, verts, (x1, y1, x2, y2)) in enumerate(components):
        cv2.rectangle(img, (x1, y1), (x2, y2), (40, 40, 40), 2)
        cv2.putText(img, str(i), (x1, max(0, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 255), 2)
    for ni, net in enumerate(nets):
        col = _NET_COLORS[ni % len(_NET_COLORS)]
        for ci, _pin in net:
            if ci < len(components):
                x1, y1, x2, y2 = components[ci][2]
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                cv2.circle(img, (cx, cy), 7, col, -1)
                cv2.putText(img, f"n{ni}", (cx + 8, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


def draw_vlm_input(gray, components, elec, out_path: Path) -> None:
    """Render the VLM-input overlay: the real scan with ELECTRICAL component boxes labelled
    by their index (no net colouring -- that would leak the connectivity GT). The VLM is
    given the detections (as the pipeline is) and tested only on connectivity; it reports
    nets by these integer indices (zero-based)."""
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for i in elec:
        x1, y1, x2, y2 = components[i][2]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(img, str(i), (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 255), 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=25, help="number of images to select")
    ap.add_argument("--images", nargs="*", help="explicit image stems (overrides selection)")
    ap.add_argument("--out", default="ground_truth/real_nets.json")
    ap.add_argument("--overlays", default="output/net_gt_overlays")
    ap.add_argument("--vlm-overlays", default="output/vlm_input_overlays",
                    help="dir for VLM-input overlays (scan + electrical component indices, no nets)")
    args = ap.parse_args()

    names = args.images or select(discover(), args.n)
    print(f"Building net-GT for {len(names)} images using base join '{GT_STRATEGY}'")

    result: dict[str, dict] = {}
    for name in names:
        img_path = _gt_images() / f"{name}_jpg.jpg"
        gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        gt_wire_file = _gt_wire_labels() / f"{name}_jpg.txt"
        if gray is None or hdc is None or not gt_wire_file.exists():
            print(f"  skip {name} (missing data)")
            continue
        h, w = gray.shape
        components = parse_components(hdc.read_text(), w, h)
        wires = parse_gt_wires(gt_wire_file.read_text(), w, h)
        if not components or not wires:
            print(f"  skip {name} (no comps/wires)")
            continue
        std_pins = make_pins(wires, components)
        junc_pins = make_pins_junction_aware(wires, components)
        _pins, nl = run_strategy(GT_STRATEGY, wires, components, std_pins=std_pins, junc_pins=junc_pins)
        nets = netlist_to_nets(nl)
        elec = electrical_indices(components)
        # per-electrical-component metadata for end-to-end VLM matching (the VLM names its
        # own components from the raw scan; we align them to these by normalized center).
        comp_meta = {}
        for i in elec:
            x1, y1, x2, y2 = components[i][2]
            comp_meta[i] = {
                "type": COMPONENT_TYPES.get(int(components[i][0]), "unknown"),
                "cx": round((x1 + x2) / 2 / w, 4),
                "cy": round((y1 + y2) / 2 / h, 4),
            }
        result[f"{name}_jpg"] = {
            "nets": nets,
            "n_components": len(components),
            "electrical_idxs": elec,
            "components": comp_meta,
            "img_wh": [w, h],
            "n_wires": len(wires),
            "source": f"perfect-GT-wires + {GT_STRATEGY} (proposal, pending human verify)",
        }
        draw_overlay(gray, components, wires, nets, Path(args.overlays) / f"{name}.png")
        draw_vlm_input(gray, components, elec, Path(args.vlm_overlays) / f"{name}.png")
        print(f"  {name}: {len(components)} comps, {len(wires)} wires, {len(nets)} nets")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {out} ({len(result)} images). Overlays: {args.overlays}")
    print("NEXT: review overlays, correct ground_truth/real_nets.json, flip 'source' to 'human-verified'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
