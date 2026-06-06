"""
Netlist / node-joining visualizer.

Takes a downloaded YOLO-OBB export (the *wires* you accepted in the viewer) plus
the YOLO-OBB *component* labels, runs the REAL production node-joining pipeline
(wire_detection.core.netlist, exactly as the /api/netlist route does), and
renders the resulting electrical nets on top of each image so you can eyeball
whether the joining of nodes is actually good.

Color legend on the output PNG:
  * Each electrical NET (node with >=2 pins) gets its own bright color. Every
    wire + pin belonging to that net is drawn in that color. So:
      - One continuous conductor shown in TWO colors  -> UNDER-join (missed merge)
      - Two clearly separate conductors in ONE color  -> OVER-join (wrong merge)
  * GREY pins  = isolated pins (a component terminal that joined to nothing).
  * RED wire + red ring = a DANGLING wire end (endpoint with no pin within
    max_pin_dist) -> the wire was detected but doesn't reach a component.
  * Thin cyan boxes = component bounding boxes (from the labels).
  * Small white dots = discovered/derived pin locations.

Usage (run from inside circuit-upstream/):
  uv run python wire_detection/benchmark/netlist_viz.py --obb-zip "C:/Users/chris/Downloads/wires_yolo_obb_XXigt.zip"
  uv run python wire_detection/benchmark/netlist_viz.py --obb-zip <zip> --limit 15
  uv run python wire_detection/benchmark/netlist_viz.py --obb-dir <extracted_dir> --labels-dir <comp_labels>

Outputs (default ../netlist_viz/<export_name>/):
  index.html        <- grid browser
  summary.csv       <- per-image join-quality metrics
  images/<stem>_netlist.png
  spice/<stem>.spice
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import html
import json
import math
import os
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from wire_detection.core.netlist import (  # noqa: E402
    build_netlist,
    derive_pins_from_obb,
    discover_pins,
)
from wire_detection.core.spice import COMPONENT_NAMES, SpiceGenerator  # noqa: E402

WORKSPACE = Path(os.environ.get("WIRE_WORKSPACE", str(SCRIPT_DIR.parent))).resolve()
DEFAULT_LABELS_DIR = WORKSPACE / "manually_verified_no_background_data" / "labels"
DEFAULT_OUT_ROOT = WORKSPACE / "netlist_viz"

# Join parameters — mirror the production defaults (api/routes/netlist.py +
# core.netlist signatures). Exposed as CLI flags so you can probe sensitivity.
CLUSTER_RADIUS = 20.0   # discover_pins DBSCAN eps
MAX_COMP_DIST = 50.0    # discover_pins endpoint->component gather radius
MAX_PIN_DIST = 30.0     # build_netlist wire-endpoint -> pin attach radius


# ───────────────────────── parsing ─────────────────────────

def obb_line_to_centerline(corners: list[tuple[float, float]]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Convert a 4-corner OBB rectangle back to its 2-point centerline using
    the midpoints of the two shortest edges (robust to corner ordering)."""
    pts = np.array(corners, dtype=np.float64)
    edges = []
    for i in range(4):
        a = pts[i]
        b = pts[(i + 1) % 4]
        edges.append((np.linalg.norm(a - b), i, (i + 1) % 4))
    edges.sort(key=lambda e: e[0])
    m1 = (pts[edges[0][1]] + pts[edges[0][2]]) / 2
    m2 = (pts[edges[1][1]] + pts[edges[1][2]]) / 2
    return (int(round(m1[0])), int(round(m1[1]))), (int(round(m2[0])), int(round(m2[1])))


def parse_wires_obb(label_text: str, w: int, h: int):
    """Parse YOLO-OBB wire labels -> list of 2-point centerlines (px)."""
    wires = []
    for line in label_text.splitlines():
        parts = line.split()
        if len(parts) != 9:
            continue
        try:
            coords = [float(x) for x in parts[1:9]]
        except ValueError:
            continue
        corners = [(coords[i] * w, coords[i + 1] * h) for i in range(0, 8, 2)]
        p1, p2 = obb_line_to_centerline(corners)
        wires.append((p1, p2))
    return wires


def parse_components(label_text: str, w: int, h: int):
    """Parse YOLO-OBB component labels -> [(cls_id, polygon, bbox)] in px."""
    comps = []
    for line in label_text.splitlines():
        parts = line.split()
        if len(parts) != 9:
            continue
        try:
            cls_id = int(parts[0])
            coords = [float(x) for x in parts[1:9]]
        except ValueError:
            continue
        xs = [int(coords[i] * w) for i in range(0, 8, 2)]
        ys = [int(coords[i] * h) for i in range(1, 8, 2)]
        polygon = [(xs[i], ys[i]) for i in range(4)]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        comps.append((cls_id, polygon, bbox))
    return comps


# ───────────────────────── join (production path) ─────────────────────────

def build_join(wires, components, cluster_radius, max_comp_dist, max_pin_dist):
    """Mirror api/routes/netlist.py::_build_netlist_data join steps exactly."""
    all_pins = []
    for ci, comp in enumerate(components):
        type_name = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        all_pins.extend(derive_pins_from_obb(ci, comp, type_name))

    clustered = discover_pins(
        wires, components,
        cluster_radius=cluster_radius, max_comp_dist=max_comp_dist,
    )
    if clustered:
        overrides = {(cp.component_idx, cp.pin_idx): (cp.x, cp.y) for cp in clustered}
        for pin in all_pins:
            key = (pin.component_idx, pin.pin_idx)
            if key in overrides:
                pin.x, pin.y = overrides[key]

    netlist = build_netlist(wires, components, all_pins, max_pin_dist=max_pin_dist)
    return all_pins, netlist


# ───────────────────────── metrics ─────────────────────────

def nearest_pin_dist(ep, pins):
    best = float("inf")
    for p in pins:
        d = math.hypot(ep[0] - p.x, ep[1] - p.y)
        if d < best:
            best = d
    return best


def compute_metrics(wires, components, pins, netlist, max_pin_dist):
    nets = [n for n in netlist.nodes if len(n.pins) >= 2]
    isolated = [n for n in netlist.nodes if len(n.pins) == 1]
    large = [n for n in netlist.nodes if len(n.pins) > 5]

    dangling_ends = 0
    for ep1, ep2 in wires:
        for ep in (ep1, ep2):
            if not pins or nearest_pin_dist(ep, pins) > max_pin_dist:
                dangling_ends += 1

    comps_connected = set()
    for n in nets:
        for p in n.pins:
            comps_connected.add(p.component_idx)

    return {
        "n_components": len(components),
        "n_wires": len(wires),
        "n_pins": len(pins),
        "n_nodes": len(netlist.nodes),
        "n_nets": len(nets),
        "n_isolated_pins": len(isolated),
        "n_large_nodes": len(large),
        "dangling_wire_ends": dangling_ends,
        "pct_components_connected": round(100.0 * len(comps_connected) / max(1, len(components)), 1),
    }


# ───────────────────────── rendering ─────────────────────────

def net_palette(n: int) -> list[tuple[int, int, int]]:
    """n visually-distinct BGR colors via golden-ratio HSV cycling."""
    colors = []
    golden = 0.61803398875
    h = 0.0
    for _ in range(max(1, n)):
        h = (h + golden) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
        colors.append((int(b * 255), int(g * 255), int(r * 255)))
    return colors


def render(image, wires, components, pins, netlist, max_pin_dist, metrics):
    canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image.copy()
    canvas = (canvas * 0.45 + 30).astype(np.uint8)  # dim base so overlay pops

    # node_id -> color (only multi-pin nets get vivid colors)
    nets = [n for n in netlist.nodes if len(n.pins) >= 2]
    palette = net_palette(len(nets))
    node_color = {n.node_id: palette[i] for i, n in enumerate(nets)}
    GREY = (140, 140, 140)

    # pin (component_idx, pin_name) -> node_id
    pin_node = dict(netlist.pin_to_node)

    # component boxes
    for ci, comp in enumerate(components):
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (120, 120, 90), 1)
        name = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        cv2.putText(canvas, name[:10], (x1, max(10, y1 - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (90, 200, 220), 1, cv2.LINE_AA)

    # wires, colored by the net of the pin(s) they attach to
    for ep1, ep2 in wires:
        d1 = nearest_pin_dist(ep1, pins) if pins else float("inf")
        d2 = nearest_pin_dist(ep2, pins) if pins else float("inf")
        end1_float = d1 > max_pin_dist
        end2_float = d2 > max_pin_dist

        # find node for whichever end attaches
        color = GREY
        for ep, floated in ((ep1, end1_float), (ep2, end2_float)):
            if floated:
                continue
            # nearest pin -> its node
            best, bestp = float("inf"), None
            for p in pins:
                dd = math.hypot(ep[0] - p.x, ep[1] - p.y)
                if dd < best:
                    best, bestp = dd, p
            if bestp is not None:
                nid = pin_node.get((bestp.component_idx, bestp.pin_name))
                if nid in node_color:
                    color = node_color[nid]
                    break

        dangling = end1_float or end2_float
        thickness = 2
        cv2.line(canvas, ep1, ep2, color, thickness, cv2.LINE_AA)
        # mark floating ends in red
        if end1_float:
            cv2.circle(canvas, ep1, 5, (0, 0, 255), 2, cv2.LINE_AA)
        if end2_float:
            cv2.circle(canvas, ep2, 5, (0, 0, 255), 2, cv2.LINE_AA)

    # pins, colored by net (grey if isolated)
    for p in pins:
        nid = pin_node.get((p.component_idx, p.pin_name))
        col = node_color.get(nid, GREY)
        cv2.circle(canvas, (p.x, p.y), 4, col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (p.x, p.y), 4, (20, 20, 20), 1, cv2.LINE_AA)

    # stats panel (top-left)
    lines = [
        f"components: {metrics['n_components']}   wires: {metrics['n_wires']}",
        f"nets (>=2 pins): {metrics['n_nets']}   isolated pins: {metrics['n_isolated_pins']}",
        f"dangling wire ends: {metrics['dangling_wire_ends']}   large nodes(>5): {metrics['n_large_nodes']}",
        f"components connected: {metrics['pct_components_connected']}%",
    ]
    y = 16
    for i, t in enumerate(lines):
        col = (230, 230, 230)
        if i == 2 and (metrics["dangling_wire_ends"] > 0 or metrics["n_large_nodes"] > 0):
            col = (90, 160, 255)
        cv2.putText(canvas, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1, cv2.LINE_AA)
        y += 18

    return canvas


def _dim_base(image):
    canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image.copy()
    return (canvas * 0.40 + 26).astype(np.uint8)


def _net_centroid(node):
    xs = [p.x for p in node.pins]
    ys = [p.y for p in node.pins]
    return int(sum(xs) / len(xs)), int(sum(ys) / len(ys))


def _pins_near(ep, candidate_pins, max_pin_dist):
    """Pins within max_pin_dist of endpoint, nearest first: [(dist, pin), ...]."""
    out = []
    for p in candidate_pins:
        d = math.hypot(ep[0] - p.x, ep[1] - p.y)
        if d <= max_pin_dist:
            out.append((d, p))
    out.sort(key=lambda x: x[0])
    return out


# Colors (BGR)
C_WIRE = (255, 180, 40)    # cyan-blue : the detected wire (the real evidence)
C_PRIMARY = (90, 255, 120)  # green     : wire-end -> its NEAREST pin (the intended join)
C_EXTRA = (40, 150, 255)    # orange    : wire-end -> EXTRA pins it also grabbed (over-join)


def render_joins(image, wires, components, pins, netlist, max_pin_dist):
    """All nets at once, drawn as REAL connections (no fake hub):
    cyan = each merging wire; green = wire-end to its nearest pin; orange =
    wire-end to extra pins it also pulled in (the over-joins)."""
    canvas = _dim_base(image)
    for comp in components:
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (70, 70, 55), 1)

    nets = [n for n in netlist.nodes if len(n.pins) >= 2]
    for node in nets:
        for wi in node.wires:
            if not (0 <= wi < len(wires)):
                continue
            ep1, ep2 = wires[wi]
            cv2.line(canvas, ep1, ep2, C_WIRE, 1, cv2.LINE_AA)
            for ep in (ep1, ep2):
                near = _pins_near(ep, node.pins, max_pin_dist)
                for j, (_d, p) in enumerate(near):
                    cv2.line(canvas, ep, (p.x, p.y), C_PRIMARY if j == 0 else C_EXTRA, 1, cv2.LINE_AA)
        for p in node.pins:
            cv2.circle(canvas, (p.x, p.y), 2, (220, 220, 220), -1, cv2.LINE_AA)
    cv2.putText(canvas, f"{len(nets)} nets | cyan=wire green=nearest-pin orange=extra-pins(over-join)",
                (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(canvas, f"{len(nets)} nets | cyan=wire green=nearest-pin orange=extra-pins(over-join)",
                (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (230, 230, 230), 1, cv2.LINE_AA)
    return canvas


def render_single_net(image, wires, components, pins, netlist, node, rank, total, max_pin_dist):
    """ONE net, drawn HONESTLY: for each wire that built this net, draw the wire
    (cyan), then from each wire-end draw GREEN to the nearest pin (the intended
    'first' join) and ORANGE to every extra pin it also grabbed within range
    (these extra grabs are what over-merges nets). Everything else faint.
    """
    canvas = _dim_base(image)

    for comp in components:
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (70, 70, 55), 1)
    for ep1, ep2 in wires:
        cv2.line(canvas, ep1, ep2, (60, 60, 60), 1, cv2.LINE_AA)

    extra_joins = 0
    for wi in node.wires:
        if not (0 <= wi < len(wires)):
            continue
        ep1, ep2 = wires[wi]
        cv2.line(canvas, ep1, ep2, C_WIRE, 2, cv2.LINE_AA)
        for ep in (ep1, ep2):
            cv2.circle(canvas, ep, 3, C_WIRE, -1, cv2.LINE_AA)
            near = _pins_near(ep, node.pins, max_pin_dist)
            for j, (_d, p) in enumerate(near):
                col = C_PRIMARY if j == 0 else C_EXTRA
                cv2.line(canvas, ep, (p.x, p.y), col, 2 if j == 0 else 1, cv2.LINE_AA)
                if j > 0:
                    extra_joins += 1

    comp_types = {}
    for p in node.pins:
        comp = components[p.component_idx]
        tname = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        comp_types[tname] = comp_types.get(tname, 0) + 1
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), C_PRIMARY, 1)
        cv2.circle(canvas, (p.x, p.y), 5, C_PRIMARY, -1, cv2.LINE_AA)
        cv2.circle(canvas, (p.x, p.y), 5, (20, 20, 20), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"{tname[:8]}.{p.pin_name}", (p.x + 6, p.y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, f"{tname[:8]}.{p.pin_name}", (p.x + 6, p.y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, C_PRIMARY, 1, cv2.LINE_AA)

    ncomp = len({p.component_idx for p in node.pins})
    types_str = ", ".join(f"{k}x{v}" for k, v in sorted(comp_types.items()))
    hdr = [
        f"net N{node.node_id}  ({rank}/{total})   {len(node.pins)} pins on {ncomp} components   {len(node.wires)} wires",
        f"types: {types_str[:90]}",
        "cyan=detected wire   green=wire-end to NEAREST pin (intended join)",
        f"orange=EXTRA pins the same wire-end also grabbed -> over-joins: {extra_joins}",
    ]
    y = 16
    for i, t in enumerate(hdr):
        col = (230, 230, 230)
        if i == 0 and ncomp > 3:
            col = (90, 160, 255)
        if i == 3 and extra_joins > 0:
            col = C_EXTRA
        cv2.putText(canvas, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1, cv2.LINE_AA)
        y += 17
    return canvas


def isolate_nets(stem, gray, wires, components, pins, netlist, out_root, max_pin_dist):
    """Write one PNG per net for a single image + a browsable stepper index."""
    nets = sorted((n for n in netlist.nodes if len(n.pins) >= 2),
                  key=lambda n: len({p.component_idx for p in n.pins}), reverse=True)
    iso_dir = out_root / f"isolate_{stem}"
    iso_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for rank, node in enumerate(nets, 1):
        canvas = render_single_net(gray, wires, components, pins, netlist, node, rank, len(nets), max_pin_dist)
        fn = f"net_{node.node_id:04d}.png"
        cv2.imwrite(str(iso_dir / fn), canvas)
        ncomp = len({p.component_idx for p in node.pins})
        rows.append((fn, node.node_id, len(node.pins), ncomp))

    parts = [
        "<!doctype html><html><head><meta charset='utf-8'><title>", html.escape(stem), " nets</title><style>",
        "body{margin:0;background:#0f1115;color:#e6e6e6;font-family:system-ui,sans-serif}",
        "#bar{position:sticky;top:0;background:#181b22;border-bottom:1px solid #2a2f3a;padding:8px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}",
        "button{background:#0f1115;color:#e6e6e6;border:1px solid #2a2f3a;border-radius:4px;padding:5px 10px;cursor:pointer}",
        "button:hover{border-color:#7aa2ff}#pos{color:#8a93a6;font-variant-numeric:tabular-nums}",
        "#stage{display:flex;align-items:center;justify-content:center;padding:12px}",
        "#stage img{max-width:100%;max-height:88vh;border:1px solid #2a2f3a;border-radius:6px}",
        ".warn{color:#ffb169;font-weight:600}</style></head><body>",
        "<div id='bar'><button onclick='step(-1)'>&larr; prev net</button>",
        "<button onclick='step(1)'>next net &rarr;</button>",
        f"<span id='pos'></span><span style='color:#8a93a6'>", html.escape(stem),
        " &middot; nets ordered by #components joined (worst over-merge first)</span></div>",
        "<div id='stage'><img id='img'></div>",
        "<script>const nets=", json.dumps([{"f": r[0], "id": r[1], "p": r[2], "c": r[3]} for r in rows]), ";",
        "let i=0;function show(){const n=nets[i];document.getElementById('img').src=n.f;",
        "document.getElementById('pos').innerHTML='net '+(i+1)+'/'+nets.length+' &middot; N'+n.id+' &middot; '+n.p+' pins on '+(n.c>3?\"<span class=warn>\"+n.c+\" components</span>\":n.c+' components');}",
        "function step(d){i=(i+d+nets.length)%nets.length;show();}",
        "window.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='j')step(1);if(e.key==='ArrowLeft'||e.key==='k')step(-1);});show();</script>",
        "</body></html>",
    ]
    (iso_dir / "index.html").write_text("".join(parts), encoding="utf-8")
    return iso_dir, len(nets)


# ───────────────────────── driver ─────────────────────────

def iter_zip_items(zip_path: Path):
    """Yield (stem, image_bytes, wire_label_text) from a YOLO-OBB export zip."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        img_names = [n for n in names if "/images/train/" in n and n.lower().endswith((".jpg", ".jpeg", ".png"))]
        for img_name in sorted(img_names):
            stem = Path(img_name).stem
            # matching label
            lbl_name = img_name.replace("/images/train/", "/labels/train/")
            lbl_name = str(Path(lbl_name).with_suffix(".txt")).replace("\\", "/")
            label_text = z.read(lbl_name).decode("utf-8") if lbl_name in names else ""
            yield stem, z.read(img_name), label_text


def iter_dir_items(obb_dir: Path):
    img_dir = obb_dir / "images" / "train"
    lbl_dir = obb_dir / "labels" / "train"
    if not img_dir.exists():  # maybe they pointed at the inner folder
        cands = list(obb_dir.glob("*/images/train"))
        if cands:
            img_dir = cands[0]
            lbl_dir = cands[0].parent.parent / "labels" / "train"
    for img_path in sorted(img_dir.glob("*")):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        lbl_path = lbl_dir / f"{img_path.stem}.txt"
        label_text = lbl_path.read_text(encoding="utf-8") if lbl_path.exists() else ""
        yield img_path.stem, img_path.read_bytes(), label_text


def write_index(out_dir: Path, rows: list[dict]) -> None:
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'><title>",
        html.escape(out_dir.name),
        "</title><style>",
        "body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:16px}",
        "h1{font-size:16px;margin:0 0 12px}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:12px}",
        ".cell{background:#181b22;border:1px solid #2a2f3a;border-radius:6px;padding:8px}",
        ".cell h3{margin:0 0 6px;font-size:12px;font-weight:600;color:#cfd6e4}",
        ".cell img{width:100%;display:block;border-radius:4px;cursor:pointer}",
        ".m{font-size:11px;color:#8a93a6;margin-top:5px;line-height:1.5}",
        ".warn{color:#ffb169;font-weight:600}",
        "</style></head><body>",
        f"<h1>{html.escape(out_dir.name)} &middot; node-joining visualization &middot; {len(rows)} images</h1>",
        "<div class='grid'>",
    ]
    for r in rows:
        warn = ""
        if r["dangling_wire_ends"] > 0 or r["n_large_nodes"] > 0 or r["pct_components_connected"] < 60:
            warn = " warn"
        parts.append(
            "<div class='cell'>"
            f"<h3>{html.escape(r['stem'])}</h3>"
            f"<a href='images/{html.escape(r['stem'])}_netlist.png' target='_blank'>"
            f"<img loading='lazy' src='images/{html.escape(r['stem'])}_netlist.png'></a>"
            f"<div class='m'>nets <b>{r['n_nets']}</b> &middot; isolated pins {r['n_isolated_pins']} "
            f"&middot; <span class='{warn.strip()}'>dangling ends {r['dangling_wire_ends']}</span> "
            f"&middot; large nodes {r['n_large_nodes']}<br>"
            f"components {r['n_components']} ({r['pct_components_connected']}% connected) &middot; wires {r['n_wires']} "
            f"&middot; <a style='color:#7af' href='spice/{html.escape(r['stem'])}.spice' target='_blank'>spice</a></div>"
            "</div>"
        )
    parts.append("</div></body></html>")
    (out_dir / "index.html").write_text("".join(parts), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--obb-zip", type=Path, help="Downloaded YOLO-OBB export .zip (wires)")
    src.add_argument("--obb-dir", type=Path, help="Extracted YOLO-OBB export dir")
    ap.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR,
                    help=f"Component YOLO-OBB labels dir (default: {DEFAULT_LABELS_DIR})")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT,
                    help=f"Output root (default: {DEFAULT_OUT_ROOT})")
    ap.add_argument("--limit", type=int, default=0, help="Only process first N images (0 = all)")
    ap.add_argument("--cluster-radius", type=float, default=CLUSTER_RADIUS)
    ap.add_argument("--max-comp-dist", type=float, default=MAX_COMP_DIST)
    ap.add_argument("--max-pin-dist", type=float, default=MAX_PIN_DIST)
    ap.add_argument("--isolate", type=str, default=None,
                    help="Stem of ONE image -> emit a per-net stepper (verify each net alone). "
                         "Only that image is processed.")
    args = ap.parse_args()

    if not args.labels_dir.exists():
        print(f"ERROR: component labels dir not found: {args.labels_dir}", file=sys.stderr)
        return 2

    if args.obb_zip:
        if not args.obb_zip.exists():
            print(f"ERROR: zip not found: {args.obb_zip}", file=sys.stderr)
            return 2
        export_name = args.obb_zip.stem
        items = iter_zip_items(args.obb_zip)
    else:
        if not args.obb_dir.exists():
            print(f"ERROR: dir not found: {args.obb_dir}", file=sys.stderr)
            return 2
        export_name = args.obb_dir.name
        items = iter_dir_items(args.obb_dir)

    out_dir = args.out_root / export_name
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "spice").mkdir(parents=True, exist_ok=True)

    print(f"[viz] export   : {export_name}")
    print(f"[viz] labels   : {args.labels_dir}")
    print(f"[viz] out      : {out_dir}")
    print(f"[viz] params   : cluster_radius={args.cluster_radius} max_comp_dist={args.max_comp_dist} max_pin_dist={args.max_pin_dist}")

    gen = SpiceGenerator()
    rows: list[dict] = []
    n_done = 0
    for stem, img_bytes, wire_text in items:
        if args.isolate and stem != args.isolate:
            continue
        if args.limit and not args.isolate and n_done >= args.limit:
            break
        arr = np.frombuffer(img_bytes, np.uint8)
        gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            print(f"  SKIP {stem}: cannot decode image")
            continue
        h, w = gray.shape

        wires = parse_wires_obb(wire_text, w, h)

        comp_label = args.labels_dir / f"{stem}.txt"
        if not comp_label.exists():
            print(f"  SKIP {stem}: no component label at {comp_label.name}")
            continue
        components = parse_components(comp_label.read_text(encoding="utf-8"), w, h)

        pins, netlist = build_join(
            wires, components,
            args.cluster_radius, args.max_comp_dist, args.max_pin_dist,
        )

        if args.isolate:
            iso_dir, n_nets = isolate_nets(stem, gray, wires, components, pins, netlist, out_dir, args.max_pin_dist)
            print(f"[isolate] {stem}: {n_nets} nets -> {iso_dir}")
            print(f"[isolate] open {iso_dir / 'index.html'}  (step with arrow keys / j,k)")
            return 0

        metrics = compute_metrics(wires, components, pins, netlist, args.max_pin_dist)
        canvas = render(gray, wires, components, pins, netlist, args.max_pin_dist, metrics)
        cv2.imwrite(str(out_dir / "images" / f"{stem}_netlist.png"), canvas)
        joins = render_joins(gray, wires, components, pins, netlist, args.max_pin_dist)
        cv2.imwrite(str(out_dir / "images" / f"{stem}_joins.png"), joins)

        try:
            spice_text = gen.generate(components, netlist)
        except Exception as exc:  # SPICE is best-effort
            spice_text = f"* SPICE generation failed: {exc}\n.end"
        (out_dir / "spice" / f"{stem}.spice").write_text(spice_text, encoding="utf-8")

        row = {"stem": stem, **metrics}
        rows.append(row)
        n_done += 1
        if n_done % 10 == 0 or n_done == 1:
            print(f"  [{n_done:4d}] {stem}  nets={metrics['n_nets']} dangling={metrics['dangling_wire_ends']} iso={metrics['n_isolated_pins']}")

    if args.isolate:
        print(f"[isolate] stem '{args.isolate}' not found in export")
        return 1
    if not rows:
        print("[viz] no images processed")
        return 1

    with open(out_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)
    write_index(out_dir, rows)

    tot_dangling = sum(r["dangling_wire_ends"] for r in rows)
    avg_conn = sum(r["pct_components_connected"] for r in rows) / len(rows)
    print(f"[done] {len(rows)} images | total dangling wire-ends={tot_dangling} | avg components-connected={avg_conn:.1f}%")
    print(f"[done] open {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
