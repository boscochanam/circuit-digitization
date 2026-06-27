import sys
import cv2
import numpy as np
from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.cc_baseline import binarize
from wire_detection.core.join_strategies import make_pins

name = sys.argv[1] if len(sys.argv) > 1 else "C20_D2_P2"
g = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
h, w = g.shape
comps = parse_components(find_hdc_label(name).read_text(), w, h)
ink = binarize(g)
print("raw ink px:", int((ink > 0).sum()))
for _c, _v, (x1, y1, x2, y2) in comps:
    cv2.rectangle(ink, (max(0, x1 - 1), max(0, y1 - 1)), (min(w - 1, x2 + 1), min(h - 1, y2 + 1)), 0, -1)
n, labels = cv2.connectedComponents(ink, 8)
sizes = np.bincount(labels.ravel())
big = [(i, int(s)) for i, s in enumerate(sizes) if i != 0 and s >= 25]
print("num blobs total:", n, "| blobs>=25px:", len(big), "| top sizes:", sorted([s for _, s in big], reverse=True)[:8])
pins = make_pins([], comps)
print("num pins:", len(pins))
vis = cv2.cvtColor(ink, cv2.COLOR_GRAY2BGR)
hit = 0
for p in pins:
    x, y = int(p.x), int(p.y)
    sub = labels[max(0, y - 26):y + 27, max(0, x - 26):x + 27]
    near = sorted(set(int(l) for l in sub.ravel() if l != 0 and sizes[l] >= 25))
    if near:
        hit += 1
    cv2.circle(vis, (x, y), 4, (0, 0, 255), -1)
print(f"pins with a blob within 26px: {hit}/{len(pins)}")
cv2.imwrite("/tmp/debug_cc.png", vis)
print("wrote /tmp/debug_cc.png")
