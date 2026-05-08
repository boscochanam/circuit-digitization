import cv2
import numpy as np
import os
import colorsys
from scipy.ndimage import label as connected_label

def parse_yolo_polygon(label_path, img_w, img_h):
    polygons = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            coords = [float(x) for x in parts[1:]]
            polygon = []
            for i in range(0, len(coords), 2):
                x = coords[i] * img_w
                y = coords[i+1] * img_h
                polygon.append([x, y])
            polygons.append(np.array(polygon, dtype=np.int32))
    return polygons

def get_distinct_color(i, total):
    hue = (i * 137.508) % 360  # golden angle for good distribution
    h = hue / 360
    rgb = colorsys.hsv_to_rgb(h, 0.85, 0.95)
    return (int(rgb[2] * 255), int(rgb[0] * 255), int(rgb[1] * 255))

def method_a(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 300)
    kernel = np.ones((5, 5), np.uint8)
    return cv2.dilate(edges, kernel, iterations=2)

base = "/home/bosco/Projects/Misc-Projects/LineDetection/roboflow_test"
img_path = f"{base}/train/images/20241004_130307_jpg.rf.78e33b9c81c31679f5719b3c5137f459.jpg"
label_path = f"{base}/train/labels/20241004_130307_jpg.rf.78e33b9c81c31679f5719b3c5137f459.txt"

img = cv2.imread(img_path)
h, w = img.shape[:2]
gt_polygons = parse_yolo_polygon(label_path, w, h)

# Get detected edges
pred = method_a(img_path)

# Use CCL to separate detected edges into individual components
labeled_edges, num_detected = connected_label(pred > 0, structure=np.ones((3,3)))

print(f"GT wires: {len(gt_polygons)}")
print(f"Detected components: {num_detected}")

# 1. GT wires - each in different color
gt_vis = img.copy()
for i, poly in enumerate(gt_polygons):
    color = get_distinct_color(i, len(gt_polygons))
    cv2.polylines(gt_vis, [poly], False, color, 2)
cv2.putText(gt_vis, f"GT: {len(gt_polygons)} wires", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.imwrite("/home/bosco/Projects/Misc-Projects/LineDetection/1_gt.png", gt_vis)

# 2. Detected edges - each component in different color
det_vis = img.copy()
for i in range(1, min(num_detected + 1, 100)):  # limit colors
    color = get_distinct_color(i, min(num_detected + 1, 100))
    mask = (labeled_edges == i).astype(np.uint8) * 255
    det_vis[mask > 0] = color
cv2.putText(det_vis, f"Detected: {num_detected} components", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.imwrite("/home/bosco/Projects/Misc-Projects/LineDetection/2_detected.png", det_vis)

# 3. Side by side comparison
combined = np.hstack([gt_vis, det_vis])
cv2.imwrite("/home/bosco/Projects/Misc-Projects/LineDetection/3_side_by_side.png", combined)

# 4. Detected = green, Missed = red, False positive = magenta
overlay = img.copy()

# Draw missed GT wires in RED
missed_count = 0
detected_count = 0
for i, poly in enumerate(gt_polygons):
    cx, cy = int(np.mean(poly[:, 0])), int(np.mean(poly[:, 1]))
    if pred[cy, cx] > 0:
        color = get_distinct_color(i, len(gt_polygons))  # colored = detected
        cv2.polylines(overlay, [poly], False, color, 2)
        detected_count += 1
    else:
        cv2.polylines(overlay, [poly], False, (0, 0, 255), 3)  # red = missed
        missed_count += 1

# Draw false positives in MAGENTA
for i in range(1, num_detected + 1):
    mask = (labeled_edges == i)
    if not np.any(mask): continue
    # Check if this component is near any GT wire
    pts = np.argwhere(mask)
    is_fp = True
    for poly in gt_polygons:
        for pt in poly:
            for det_pt in pts:
                if np.linalg.norm(det_pt - pt) < 20:
                    is_fp = False
                    break
            if not is_fp:
                break
        if not is_fp:
            break
    if is_fp:
        overlay[mask] = (255, 0, 255)  # magenta = false positive

# Add legend
cv2.putText(overlay, f"Detected: {detected_count} (colored)", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
cv2.putText(overlay, f"Missed: {missed_count} (RED)", (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
cv2.putText(overlay, f"False pos: {num_detected - detected_count} (MAGENTA)", (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

cv2.imwrite("/home/bosco/Projects/Misc-Projects/LineDetection/4_comparison.png", overlay)

print("\nSaved:")
print("  1_gt.png - GT wires each with unique color")
print("  2_detected.png - Each detected component unique color")
print("  3_side_by_side.png - GT left, detected right")
print("  4_comparison.png - Colored=detected, RED=missed, MAGENTA=false positive")