"""Three-stage visualization: Ground Truth → Error Injected → After Join.

For each circuit: 3 panels side-by-side showing:
  1. Ground truth (clean wires + correct connections)
  2. Error-injected (detector-style perturbation)
  3. After join (graph_rescue recovery)

Components drawn as colored boxes, pins as yellow dots,
wires as lines (green=correct, red=displaced, blue=recovered).
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.synthgt.synthesize import (
    synthesize_clean, inject_errors, ERROR_LEVELS, pin_positions,
)
from wire_detection.core.join_strategies import run_strategy
from wire_detection.core.component_assignment import snap_endpoint

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
except Exception:
    FNT = FNT_R = lambda s: ImageFont.load_default()

font_title = FNT(18)
font_stage = FNT(14)
font_sub = FNT_R(11)
font_comp = FNT(10)
font_pin = FNT_R(8)
font_legend = FNT_R(9)

TYPE_COL = {
    "voltage-DC": ("#7f1d1d", "#ef4444"),
    "resistor":   ("#14532d", "#22c55e"),
    "inductor":   ("#164e63", "#06b6d4"),
    "diode":      ("#78350f", "#f59e0b"),
    "gnd":        ("#374151", "#9ca3af"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R", "inductor": "L", "diode": "D", "gnd": "GND"}

WIRE_GT = "#22c55e"       # ground truth
WIRE_ERR = "#ef4444"      # error-injected
WIRE_RECOV = "#3b82f6"    # after join (recovered)
WIRE_MISS = "#f97316"     # endpoint that didn't connect
PIN_COL = "#facc15"
EP_COL = "#ffffff"


def rotated_rect(cx, cy, w, h, angle_deg):
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    half_w, half_h = w / 2, h / 2
    corners = [(-half_w, -half_h), (half_w, -half_h),
               (half_w, half_h), (-half_w, half_h)]
    return [(int(cos_a * dx - sin_a * dy + cx),
             int(sin_a * dx + cos_a * dy + cy))
            for dx, dy in corners]


def get_transform(spec, pw, ph):
    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs) - 80, max(xs) + 80
    min_y, max_y = min(ys) - 80, max(ys) + 80
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1
    pad = 40
    sc = min((pw - 2 * pad) / range_x, (ph - 2 * pad - 10) / range_y)
    def tx(x): return pad + (x - min_x) * sc
    def ty(y): return pad + 10 + (y - min_y) * sc
    return tx, ty, sc


def draw_components(draw, spec, sx, sy, sc):
    for i, c in enumerate(spec.comps):
        fill, border = TYPE_COL.get(c.type, ("#333", "#666"))
        prefix = TYPE_PREFIX.get(c.type, "?")
        if c.orient == "H":
            raw_w, raw_h = c.size, 30
        else:
            raw_w, raw_h = 30, c.size
        angle = getattr(c, "angle", 0.0) or 0.0
        bw, bh = raw_w * sc, raw_h * sc
        corners = rotated_rect(sx(c.cx), sy(c.cy), max(bw, 20), max(bh, 14), angle)
        draw.polygon(corners, fill=fill, outline=border, width=2)
        draw.text((sx(c.cx), sy(c.cy)), f"{prefix}{i+1}",
                  fill="#fff", font=font_comp, anchor="mm")


def draw_pins(draw, pin_pos, sx, sy):
    for (ci, pi), (px, py) in pin_pos.items():
        x, y = sx(px), sy(py)
        draw.ellipse([x-3, y-3, x+3, y+3], fill=PIN_COL, outline="#000", width=1)


def draw_wires(draw, wires, sx, sy, color, width=2):
    for w in wires:
        draw.line([(sx(w[0][0]), sy(w[0][1])), (sx(w[1][0]), sy(w[1][1]))],
                  fill=color, width=width)
    # endpoints
    for w in wires:
        for ep in w:
            r = 2
            draw.ellipse([sx(ep[0])-r, sy(ep[1])-r, sx(ep[0])+r, sy(ep[1])+r], fill=EP_COL)


def draw_panel(img, spec, wires, pin_pos, cx, cy, pw, ph, title, wire_color, show_endpoints=True):
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([cx, cy, cx + pw, cy + ph],
                           radius=6, fill="#1e293b", outline="#334155", width=1)
    draw.text((cx + pw // 2, cy + 8), title, fill="#e94560", font=font_stage, anchor="mt")

    tx, ty, sc = get_transform(spec, pw, ph)
    ox, oy = cx, cy
    sx = lambda x: ox + tx(x)
    sy = lambda y: oy + ty(y)

    draw_wires(draw, wires, sx, sy, wire_color)
    draw_components(draw, spec, sx, sy, sc)
    draw_pins(draw, pin_pos, sx, sy)


def get_join_connections(err_wires, components):
    """Run join and return which endpoints connected (as sets of pin keys)."""
    result = run_strategy("graph_rescue", err_wires, components)
    net = result[1]  # (pins, netlist)
    # Map wire endpoints to nodes
    connected = []
    for w in err_wires:
        ep1_connected = False
        ep2_connected = False
        for (ci, pi), nid in net.pin_to_node.items():
            # Check if endpoint is close to any pin on this node
            pass
        connected.append((ep1_connected, ep2_connected))
    return net


def make_three_panel(circuit_name, spec, pw=420, ph=340, seed=0, error_level=3):
    """Create a 3-panel image for one circuit: GT → Error → Joined."""
    components, clean_wires, pin_pos = synthesize_clean(spec)
    err_wires = inject_errors(clean_wires, error_level, seed, pin_pos=pin_pos)
    
    # Run join on error wires (pass correct pins)
    from wire_detection.synthgt.evaluate import _make_std_pins
    std_pins = _make_std_pins(pin_pos, spec)
    result = run_strategy("graph_rescue", err_wires, components, std_pins=std_pins)
    pins, net = result
    
    # Determine connection status from the actual join result (union-find)
    # A wire endpoint is "connected" if its union-find root contains any pin
    from collections import defaultdict
    ep_roots = {}  # (w_idx, ep_idx) -> root
    pin_roots = set()  # roots that contain pins
    for (ci, pi), nid in net.pin_to_node.items():
        pin_roots.add(nid)
    
    # We need to run the graph builder to get the union-find state
    # Instead, check if the wire's endpoints share a node with any pin
    # by checking if both endpoints' components are in the same node
    wire_connected = []
    for w_idx, w in enumerate(err_wires):
        # Check if this wire's endpoints are assigned to components that are connected
        ep0_comp = None
        ep1_comp = None
        # Find which component each endpoint is nearest to
        for ci, (cls, verts, bbox) in enumerate(components):
            x1, y1, x2, y2 = bbox
            for ep_idx, ep in enumerate(w):
                if x1 <= ep[0] <= x2 and y1 <= ep[1] <= y2:
                    if ep_idx == 0:
                        ep0_comp = ci
                    else:
                        ep1_comp = ci
        # Check if those components are in the same node
        if ep0_comp is not None and ep1_comp is not None:
            node0 = net.pin_to_node.get((ep0_comp, 'pin0'))
            node1 = net.pin_to_node.get((ep1_comp, 'pin0'))
            if node0 is not None and node1 is not None and node0 == node1:
                wire_connected.append(True)
                continue
        # Fallback: check if either endpoint is inside a component bbox
        # and that component is in a node with other components
        connected = False
        for ep_idx, ep in enumerate(w):
            for ci, (cls, verts, bbox) in enumerate(components):
                x1, y1, x2, y2 = bbox
                if x1 <= ep[0] <= x2 and y1 <= ep[1] <= y2:
                    # This endpoint is inside a component
                    node = net.pin_to_node.get((ci, 'pin0'))
                    if node is not None:
                        # Check if this node has pins from other components
                        other_comps = set()
                        for (pci, ppi), nid in net.pin_to_node.items():
                            if nid == node and pci != ci:
                                other_comps.add(pci)
                        if other_comps:
                            connected = True
                            break
            if connected:
                break
        wire_connected.append(connected)

    # Build joined wires: green if both endpoints connected, yellow if one, red if none
    joined_wires = []
    for w_idx, w in enumerate(err_wires):
        is_connected = wire_connected[w_idx]
        if is_connected:
            color = WIRE_RECOV  # blue = fully recovered
        else:
            color = WIRE_MISS   # orange = disconnected
        joined_wires.append((w, color))

    W = pw * 3 + 40  # 3 panels + gaps
    H = ph + 80       # panel + title + legend
    img = Image.new("RGB", (W, H), "#111827")
    draw = ImageDraw.Draw(img)

    # Title
    draw.text((W // 2, 10), f"{circuit_name}  ({len(spec.comps)} components, {len(spec.nets)} nets)",
              fill="#e94560", font=font_title, anchor="mt")

    # Stage 1: Ground Truth
    draw_panel(img, spec, clean_wires, pin_pos, 15, 45, pw, ph, "Ground Truth", WIRE_GT)

    # Stage 2: Error Injected
    draw_panel(img, spec, err_wires, pin_pos, pw + 25, 45, pw, ph, f"Error Injected (L{error_level})", WIRE_ERR)

    # Stage 3: After Join — snap recovered endpoints to their pin positions
    cx3 = 2 * pw + 35
    draw.rounded_rectangle([cx3, 45, cx3 + pw, 45 + ph], radius=6, fill="#1e293b", outline="#334155", width=1)
    draw.text((cx3 + pw // 2, 53), f"After Join (graph_rescue)", fill="#e94560", font=font_stage, anchor="mt")
    
    tx, ty, sc = get_transform(spec, pw, ph)
    sx = lambda x: cx3 + tx(x)
    sy = lambda y: 45 + ty(y)
    
    # Draw joined wires with snapped endpoints for recovered wires
    for w_idx, (w, color) in enumerate(joined_wires):
        if wire_connected[w_idx]:
            # Snap both endpoints to their pin positions (using shared utility)
            ep0_snap = snap_endpoint(w[0], components, pin_pos)
            ep1_snap = snap_endpoint(w[1], components, pin_pos)
            draw.line([(sx(ep0_snap[0]), sy(ep0_snap[1])), (sx(ep1_snap[0]), sy(ep1_snap[1]))],
                      fill=color, width=2)
            # Draw small snap indicators
            for ep_snap in [ep0_snap, ep1_snap]:
                if ep_snap != ep0_snap or ep_snap != ep1_snap:
                    pass  # skip if no change
                r = 3
                draw.ellipse([sx(ep_snap[0])-r, sy(ep_snap[1])-r, sx(ep_snap[0])+r, sy(ep_snap[1])+r], 
                            fill=color, outline="#fff", width=1)
        else:
            # Disconnected — draw at original displaced position
            draw.line([(sx(w[0][0]), sy(w[0][1])), (sx(w[1][0]), sy(w[1][1]))],
                      fill=color, width=2)
            for ep in w:
                r = 2
                draw.ellipse([sx(ep[0])-r, sy(ep[1])-r, sx(ep[0])+r, sy(ep[1])+r], fill=EP_COL)
    
    draw_components(draw, spec, sx, sy, sc)
    draw_pins(draw, pin_pos, sx, sy)

    # Legend at bottom
    ly = H - 25
    lx = 15
    items = [
        (WIRE_GT, "GT wire"),
        (WIRE_ERR, "Error wire"),
        (WIRE_RECOV, "Recovered"),
        ("#a855f7", "Partial"),
        (WIRE_MISS, "Disconnected"),
        (PIN_COL, "Pin"),
    ]
    for color, label in items:
        draw.ellipse([lx, ly, lx + 8, ly + 8], fill=color)
        draw.text((lx + 12, ly), label, fill="#9ca3af", font=font_legend, anchor="lt")
        lx += draw.textlength(label, font=font_legend) + 24

    # F1 score annotation
    gt_pairs = set()
    from itertools import combinations
    node_comps = {}
    for (ci, _pin), nid in net.pin_to_node.items():
        node_comps.setdefault(nid, set()).add(ci)
    got_pairs = set()
    for comps_set in node_comps.values():
        got_pairs.update(combinations(sorted(comps_set), 2))
    
    # Ground truth pairs from spec
    gt_pairs = set()
    for net_def in spec.nets:
        comp_idxs = [ci for ci, _pi in net_def]
        gt_pairs.update(combinations(sorted(comp_idxs), 2))
    
    tp = len(gt_pairs & got_pairs)
    prec = tp / len(got_pairs) if got_pairs else (1.0 if not gt_pairs else 0.0)
    rec = tp / len(gt_pairs) if gt_pairs else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    
    draw.text((cx3 + pw // 2, 45 + ph - 15),
              f"F1={f1:.2f}  P={prec:.2f}  R={rec:.2f}",
              fill="#facc15", font=font_sub, anchor="mt")

    return img


# Generate for all circuits
SEED = 0
ERR_LEVEL = 3
OUT_DIR = "/home/claw/circuit-digitization/docs"

for spec in CATALOG:
    img = make_three_panel(spec.name, spec, seed=SEED, error_level=ERR_LEVEL)
    out = f"{OUT_DIR}/synthgt_3panel_{spec.name}.png"
    img.save(out, "PNG")
    print(f"Saved {out} ({img.width}x{img.height})")

print("\nDone — all 11 circuits rendered.")
