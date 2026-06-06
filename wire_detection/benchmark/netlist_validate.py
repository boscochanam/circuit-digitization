"""
Join-health scorecard — validate node-joining WITHOUT ground-truth netlists.

It runs the real core.netlist join (same as the UI / api) on a downloaded
OBB export and counts *structural* errors that are wrong by the laws of
circuits, no annotation required:

  HARD ERRORS (almost always wrong)
    * self_loop_components : a 2-terminal part (R/C/L/D) whose BOTH legs land
                             on the SAME net -> the part is shorted out.
    * floating_components  : a part whose pins share a net with NO other part
                             -> it connects to nothing (under-join).

  STRONG SUSPECTS (usually wrong, a few may be real power/ground rails)
    * giant_nets           : a net spanning > --giant distinct components
                             -> over-merge (the "everything is one blob" bug).
    * dangling_wire_ends   : wire endpoint not within max_pin_dist of any pin.

  RATIOS (sanity, not pass/fail)
    * nets_per_component   : healthy circuits sit ~0.5-1.0. Far below = over-
                             merge (few mega-nets); ~1.0+ with many isolated
                             pins = under-merge (nothing joined).

Outputs <out>/validate_<export>.csv (per image) and prints an aggregate
scorecard + the worst images. Track the composite score across versions:
lower = better.

Usage (from circuit-upstream/):
  uv run python wire_detection/benchmark/netlist_validate.py --obb-zip "C:/Users/chris/Downloads/wires_yolo_obb_XXXX.zip"
  uv run python wire_detection/benchmark/netlist_validate.py --obb-zip <zip> --max-pin-dist 45   # probe a change
"""
from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# reuse the exact parsing + production join from the visualizer
from netlist_viz import (  # noqa: E402
    DEFAULT_LABELS_DIR,
    DEFAULT_OUT_ROOT,
    build_join,
    nearest_pin_dist,
    parse_components,
    parse_wires_obb,
)
from wire_detection.core.mapping import TWO_TERMINAL_TYPES  # noqa: E402
from wire_detection.core.spice import COMPONENT_NAMES  # noqa: E402

# Types we expect to be electrically "inert" connectors — not errors if they
# only touch one net (junctions/terminals join wires; gnd is a rail).
INERT_TYPES = {"junction", "terminal", "gnd", "antenna", "probe", "crossover", "wire"}


def validate_one(wires, components, pins, netlist, max_pin_dist, giant_thresh):
    pin_node = dict(netlist.pin_to_node)  # (comp_idx, pin_name) -> node_id

    # node_id -> set of distinct component indices touching it
    node_comps: dict[int, set[int]] = {}
    for (ci, _pname), nid in pin_node.items():
        node_comps.setdefault(nid, set()).add(ci)

    # pins grouped per component
    comp_pins: dict[int, list] = {}
    for p in pins:
        comp_pins.setdefault(p.component_idx, []).append(p)

    self_loops = 0
    floating = 0
    connected_non_inert = 0
    non_inert = 0
    for ci, comp in enumerate(components):
        tname = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        my_pins = comp_pins.get(ci, [])
        my_nodes = [pin_node.get((ci, p.pin_name)) for p in my_pins]
        my_nodes = [n for n in my_nodes if n is not None]

        # connected if any of my nodes also holds another component's pin
        is_conn = any(len(node_comps.get(n, set())) >= 2 for n in my_nodes)
        if tname not in INERT_TYPES:
            non_inert += 1
            if is_conn:
                connected_non_inert += 1
            else:
                floating += 1

        # self-loop: 2-terminal part with >=2 pins collapsed onto one node
        if tname in TWO_TERMINAL_TYPES and len(my_nodes) >= 2:
            if len(set(my_nodes)) < len(my_nodes):
                self_loops += 1

    giant_nets = sum(1 for nid, cs in node_comps.items() if len(cs) > giant_thresh)

    dangling = 0
    for ep1, ep2 in wires:
        for ep in (ep1, ep2):
            if not pins or nearest_pin_dist(ep, pins) > max_pin_dist:
                dangling += 1

    nets = [n for n in netlist.nodes if len(n.pins) >= 2]
    n_comp = len(components)

    return {
        "n_components": n_comp,
        "n_wires": len(wires),
        "n_nets": len(nets),
        "self_loop_components": self_loops,
        "floating_components": floating,
        "giant_nets": giant_nets,
        "dangling_wire_ends": dangling,
        "pct_nonInert_connected": round(100.0 * connected_non_inert / max(1, non_inert), 1),
        "nets_per_component": round(len(nets) / max(1, n_comp), 2),
    }


def iter_zip(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        imgs = [n for n in names if "/images/train/" in n and n.lower().endswith((".jpg", ".jpeg", ".png"))]
        for img in sorted(imgs):
            lbl = str(Path(img.replace("/images/train/", "/labels/train/")).with_suffix(".txt")).replace("\\", "/")
            txt = z.read(lbl).decode("utf-8") if lbl in names else ""
            yield Path(img).stem, z.read(img), txt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obb-zip", type=Path, required=True)
    ap.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pin-dist", type=float, default=30.0)
    ap.add_argument("--cluster-radius", type=float, default=20.0)
    ap.add_argument("--max-comp-dist", type=float, default=50.0)
    ap.add_argument("--giant", type=int, default=8, help="net spanning > this many components = giant (over-merge)")
    args = ap.parse_args()

    if not args.obb_zip.exists():
        print(f"ERROR: zip not found: {args.obb_zip}", file=sys.stderr)
        return 2

    export = args.obb_zip.stem
    out_dir = args.out_root / export
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"validate_{export}.csv"

    rows = []
    n = 0
    for stem, img_bytes, wire_text in iter_zip(args.obb_zip):
        if args.limit and n >= args.limit:
            break
        gray = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        comp_label = args.labels_dir / f"{stem}.txt"
        if not comp_label.exists():
            continue
        wires = parse_wires_obb(wire_text, w, h)
        components = parse_components(comp_label.read_text(encoding="utf-8"), w, h)
        pins, netlist = build_join(wires, components, args.cluster_radius, args.max_comp_dist, args.max_pin_dist)
        m = validate_one(wires, components, pins, netlist, args.max_pin_dist, args.giant)
        rows.append({"stem": stem, **m})
        n += 1

    if not rows:
        print("No images processed.")
        return 1

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)

    # ── aggregate scorecard ──
    def tot(k):
        return sum(r[k] for r in rows)

    n_img = len(rows)
    comp_tot = tot("n_components")
    self_loops = tot("self_loop_components")
    floating = tot("floating_components")
    giant = tot("giant_nets")
    dangling = tot("dangling_wire_ends")
    avg_conn = sum(r["pct_nonInert_connected"] for r in rows) / n_img
    avg_ratio = sum(r["nets_per_component"] for r in rows) / n_img

    # composite: structural errors per component (lower=better)
    composite = round((self_loops + floating + giant) / max(1, comp_tot), 4)

    print("=" * 64)
    print(f"JOIN-HEALTH SCORECARD  ({export})")
    print(f"  images={n_img}  components={comp_tot}  max_pin_dist={args.max_pin_dist}  giant>{args.giant}")
    print("-" * 64)
    print(f"  HARD ERRORS")
    print(f"    self-loop components : {self_loops:5d}   ({self_loops / max(1, comp_tot) * 100:.1f}% of comps)")
    print(f"    floating components  : {floating:5d}   ({floating / max(1, comp_tot) * 100:.1f}% of comps)")
    print(f"  SUSPECTS")
    print(f"    giant nets (>{args.giant} comps): {giant:5d}   (over-merge)")
    print(f"    dangling wire ends   : {dangling:5d}")
    print(f"  RATIOS")
    print(f"    non-inert connected  : {avg_conn:.1f}%   (want high)")
    print(f"    nets / component     : {avg_ratio:.2f}    (~0.5-1.0 healthy; far below = over-merge)")
    print("-" * 64)
    print(f"  COMPOSITE (struct errors / component, lower=better): {composite}")
    print("=" * 64)

    worst = sorted(rows, key=lambda r: (r["self_loop_components"] + r["floating_components"] + r["giant_nets"]), reverse=True)[:10]
    print("worst images (self-loops + floating + giant):")
    for r in worst:
        print(f"  {r['stem']:24s} self={r['self_loop_components']:2d} float={r['floating_components']:2d} "
              f"giant={r['giant_nets']:2d} dangling={r['dangling_wire_ends']:2d} "
              f"nets/comp={r['nets_per_component']}")
    print(f"\ncsv -> {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
