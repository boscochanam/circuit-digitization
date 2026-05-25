#!/usr/bin/env python3
"""
REFERENCE PIPELINE — Reproducible F1=0.707 (baseline)

This is the canonical baseline implementation. Every preprocessing step is documented.
Run: uv run python wire_detection/benchmark/reference_pipeline.py

Produces F1=0.707 on the 23-image ground-truth dataset.

For the current best config (F1=0.749), run:
  uv run python -m wire_detection.benchmark.experiment_harness --preset wave2
(see best_candidate_v4 experiment)

PREPROCESSING (MANDATORY — skipping any step degrades results):
1. HDC Label Matching: find matching YOLO-OBB labels from roboflow_test2
2. Component Occlusion: fill each HDC component polygon with local median color
3. ROI Crop: tight crop around all components + 10px padding

DETECTION (baseline params):
4. Sauvola threshold (k=0.30, window=51)
5. Binary invert
6. Morphological close (ellipse 3×3)
7. CCL (min_area=20)
8. Endpoint fitting (farthest corner pairs)
9. Dedup (angle=10°, distance=18px)
   NO merge, NO length filter — both were proven harmful

DEPENDENCIES:
- Ground truth images: /home/claw/workspace/ground_truth/labels_few_annot/images/
- Ground truth labels: /home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images/
- HDC labels: /home/claw/circuit-digitization/roboflow_test2/{train,valid,test}/labels/
"""

import math
import os
import time
from pathlib import Path
import numpy as np
import cv2

# ── Paths ────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
GT_IMAGES = Path(
    os.environ.get(
        "WIRE_GT_IMAGES",
        REPO_ROOT / "labels_few_annot" / "images",
    )
)
GT_LABELS = Path(
    os.environ.get(
        "WIRE_GT_LABELS",
        REPO_ROOT
        / "labels_few_annot"
        / "labels"
        / "train"
        / "manually_verified_no_background_data"
        / "images",
    )
)
HDC_BASE = Path(os.environ.get("WIRE_HDC_BASE", REPO_ROOT / "roboflow_test2"))
HDC_SPLITS = [split.strip() for split in os.environ.get("WIRE_HDC_SPLITS", "train,valid,test").split(",") if split.strip()]

# ── Pipeline Parameters (DO NOT CHANGE — these produce F1=0.707) ──
SAUVOLA_K         = 0.30
SAUVOLA_WINDOW    = 51
SAUVOLA_FALLBACK  = 0.25
CLOSE_KERNEL      = 3
CCL_MIN_AREA      = 20
DEDUP_ANGLE       = 10   # degrees
DEDUP_DIST        = 18   # pixels
CROP_PADDING      = 10   # pixels around component ROI
OCCLUSION_MARGIN  = 0.15 # 15% margin around component boxes
GT_MATCH_DIST     = 20   # pixels — distance threshold for counting a TP


# ═══════════════════════════════════════════════════════════════
# STEP 1: HDC LABEL MATCHING
# ═══════════════════════════════════════════════════════════════
# Each ground-truth image must be paired with its HDC component
# labels. We match by comparing the image pixel content against
# all HDC images to find the corresponding label file.

def find_hdc_label(image_name: str, gray_image: np.ndarray) -> Path | None:
    """
    Find the YOLO-OBB label file from roboflow_test2 that matches
    the given ground-truth image. Uses pixel-difference matching.

    Returns the Path to the label file, or None if no match found.
    """
    best_label, best_diff = None, float("inf")
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        image_dir = HDC_BASE / split / "images"
        for label_path in label_dir.glob(f"{image_name}_jpg*"):
            # Find corresponding image
            for ext in ['.jpg', '.jpeg', '.png']:
                img_path = image_dir / f"{label_path.stem}{ext}"
                if img_path.exists():
                    break
            else:
                continue
            hdc_img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if hdc_img is None or hdc_img.shape != gray_image.shape:
                continue
            diff = cv2.absdiff(gray_image, hdc_img).mean()
            if diff < best_diff:
                best_diff = diff
                best_label = label_path
    return best_label


# ═══════════════════════════════════════════════════════════════
# STEP 2: HDC COMPONENT PARSING
# ═══════════════════════════════════════════════════════════════

def parse_components(label_path: Path, img_w: int, img_h: int) -> list:
    """
    Parse YOLO-OBB label file into component definitions.
    Each component: (class_id, polygon_points, bounding_box)
    where polygon_points is a list of 4 (x,y) tuples and
    bounding_box is (x1, y1, x2, y2).
    """
    components = []
    if label_path is None:
        return components
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 9:
                continue
            cls_id = int(parts[0])
            coords = [float(x) for x in parts[1:9]]
            # Denormalize from YOLO format
            xs = [int(coords[i] * img_w) for i in range(0, 8, 2)]
            ys = [int(coords[i+1] * img_h) for i in range(0, 8, 2)]
            polygon = [(xs[i], ys[i]) for i in range(4)]
            bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
            components.append((cls_id, polygon, bbox))
    return components


# ═══════════════════════════════════════════════════════════════
# STEP 3: COMPONENT OCCLUSION
# ═══════════════════════════════════════════════════════════════
# Fill each HDC component polygon with the local median pixel
# color. This removes component content before wire detection,
# preventing false positives from component edges/structures.

def occlude_components(gray: np.ndarray, components: list) -> np.ndarray:
    """
    Fill all component polygons with their local median background color.
    The margin around each component is OCCLUSION_MARGIN (15% of bbox size).
    """
    h, w = gray.shape
    occluded = gray.copy()
    for _, polygon, (x1, y1, x2, y2) in components:
        # Expand bounding box by margin to sample background
        margin_x = max(int((x2 - x1) * OCCLUSION_MARGIN), 5)
        margin_y = max(int((y2 - y1) * OCCLUSION_MARGIN), 5)
        sx = max(0, x1 - margin_x)
        sy = max(0, y1 - margin_y)
        ex = min(w, x2 + margin_x)
        ey = min(h, y2 + margin_y)

        # Use median color of the local region as fill
        if (ey - sy) * (ex - sx) > 0:
            fill_color = int(np.median(gray[sy:ey, sx:ex]))
        else:
            fill_color = 255

        cv2.fillPoly(occluded, [np.array(polygon, dtype=np.int32)], fill_color)
    return occluded


# ═══════════════════════════════════════════════════════════════
# STEP 4: ROI CROP
# ═══════════════════════════════════════════════════════════════
# Crop to the tight bounding box of all components + padding.
# This eliminates border artifacts from the scanner/paper edges.

def crop_to_roi(image: np.ndarray, components: list) -> tuple:
    """
    Crop image to the bounding box of all components + CROP_PADDING.
    Returns (cropped_image, offset_x, offset_y).
    """
    h, w = image.shape
    if not components:
        return image, 0, 0

    # Union of all component bounding boxes
    x1 = min(b[0] for _, _, b in components)
    y1 = min(b[1] for _, _, b in components)
    x2 = max(b[2] for _, _, b in components)
    y2 = max(b[3] for _, _, b in components)

    # Add padding, clamp to image bounds
    rx1 = max(0, x1 - CROP_PADDING)
    ry1 = max(0, y1 - CROP_PADDING)
    rx2 = min(w, x2 + CROP_PADDING)
    ry2 = min(h, y2 + CROP_PADDING)

    return image[ry1:ry2, rx1:rx2], rx1, ry1


# ═══════════════════════════════════════════════════════════════
# STEPS 5-9: WIRE DETECTION (Sauvola+CCL+Dedup)
# ═══════════════════════════════════════════════════════════════

def detect_wires(image: np.ndarray) -> list:
    """
    Full Sauvola+CCL+Dedup pipeline.

    Parameters are fixed to the proven best values.
    NO merge step — it destroys true positives.
    NO length filter — the CCL area filter is sufficient.
    """
    img_f = image.astype(np.float32)

    # 5. Sauvola threshold
    mean = cv2.boxFilter(img_f, -1, (SAUVOLA_WINDOW, SAUVOLA_WINDOW), normalize=True)
    sqr = cv2.boxFilter(img_f ** 2, -1, (SAUVOLA_WINDOW, SAUVOLA_WINDOW), normalize=True)
    std = np.sqrt(np.maximum(sqr - mean ** 2, 0))
    bw = (image > mean * (1 + SAUVOLA_K * (std / 128 - 1))).astype(np.uint8) * 255

    # 6. Invert (wires = white foreground)
    bw = cv2.bitwise_not(bw)

    # 7. Morphological close — bridge small gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (CLOSE_KERNEL, CLOSE_KERNEL))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)

    # 8. Connected component labeling
    nlab, labels, stats, _ = cv2.connectedComponentsWithStats(closed)

    # 9. Extract endpoints + dedup
    lines = []
    for i in range(1, nlab):
        if stats[i, cv2.CC_STAT_AREA] < CCL_MIN_AREA:
            continue

        mask = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        cnt = max(contours, key=cv2.contourArea)

        # Farthest corner endpoint fitting
        pts = [
            tuple(cnt[cnt[:, :, 0].argmin()][0]),   # leftmost
            tuple(cnt[cnt[:, :, 0].argmax()][0]),   # rightmost
            tuple(cnt[cnt[:, :, 1].argmin()][0]),   # topmost
            tuple(cnt[cnt[:, :, 1].argmax()][0]),   # bottommost
        ]
        best_dist, best_pair = -1, None
        for a in range(4):
            for b in range(a + 1, 4):
                d = (pts[a][0] - pts[b][0]) ** 2 + (pts[a][1] - pts[b][1]) ** 2
                if d > best_dist:
                    best_dist = d
                    best_pair = (pts[a], pts[b])
        if best_pair:
            lines.append(best_pair)

    # 10. Dedup — remove redundant overlapping detections
    if len(lines) > 1:
        lines = _dedup(lines, angle_thresh=DEDUP_ANGLE, dist_thresh=DEDUP_DIST)

    return lines


def _dedup(lines: list, angle_thresh: float = 10, dist_thresh: float = 18) -> list:
    """Remove shorter of two collinear nearby line segments."""
    at = math.radians(angle_thresh)
    kept = list(lines)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(kept):
            j = i + 1
            while j < len(kept):
                p1, p2 = kept[i]
                q1, q2 = kept[j]

                dx1, dy1 = p2[0] - p1[0], p2[1] - p1[1]
                dx2, dy2 = q2[0] - q1[0], q2[1] - q1[1]
                l1 = math.hypot(dx1, dy1)
                l2 = math.hypot(dx2, dy2)

                if l1 < 1 or l2 < 1:
                    j += 1
                    continue

                # Check angle similarity
                cos_a = (dx1 * dx2 + dy1 * dy2) / (l1 * l2)
                angle = math.acos(max(-1, min(1, cos_a)))
                if angle > at:
                    j += 1
                    continue

                # Keep longer, check if shorter is within distance
                longer = kept[i] if l1 >= l2 else kept[j]
                shorter = kept[j] if l1 >= l2 else kept[i]

                if _point_to_segment_dist(shorter[0], longer[0], longer[1]) <= dist_thresh and \
                   _point_to_segment_dist(shorter[1], longer[0], longer[1]) <= dist_thresh:
                    kept.pop(j)
                    changed = True
                else:
                    j += 1
            i += 1
    return kept


def _point_to_segment_dist(p, a, b):
    """Perpendicular distance from point p to line segment ab."""
    ax, ay = a
    bx, by = b
    px, py = p
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-8)
    t = max(0, min(1, t))
    return math.hypot(px - (ax + t * abx), py - (ay + t * aby))


# ═══════════════════════════════════════════════════════════════
# EVALUATION
# ═══════════════════════════════════════════════════════════════

def load_ground_truth(label_path: Path, img_w: int, img_h: int) -> list:
    """Parse ground-truth wire labels from YOLO-OBB format."""
    lines = []
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            try:
                coords = [float(x) for x in parts[1:9]]
                poly = np.array([[int(coords[i] * img_w), int(coords[i + 1] * img_h)]
                                 for i in range(0, 8, 2)], dtype=np.int32)
                # Short-edge midpoint method
                edges = [(i, (i + 1) % 4) for i in range(4)]
                edge_lengths = [(np.linalg.norm(poly[a] - poly[b]), a, b) for a, b in edges]
                edge_lengths.sort(key=lambda x: x[0])
                m1 = (poly[edge_lengths[0][1]] + poly[edge_lengths[0][2]]) / 2
                m2 = (poly[edge_lengths[1][1]] + poly[edge_lengths[1][2]]) / 2
                lines.append(((int(m1[0]), int(m1[1])), (int(m2[0]), int(m2[1]))))
            except (ValueError, IndexError):
                continue
    return lines


def evaluate(detected: list, ground_truth: list, match_dist: float = GT_MATCH_DIST):
    """
    Evaluate detected lines against ground truth.
    Returns (tp, fp, fn, redundant).
    Redundant = additional detections matching an already-matched GT line.
    """
    matched = [False] * len(ground_truth)
    tp = fp = red = 0

    for det in detected:
        best_dist, best_idx = float("inf"), -1
        for gi, gt in enumerate(ground_truth):
            dist = (_point_to_segment_dist(det[0], gt[0], gt[1]) +
                    _point_to_segment_dist(det[1], gt[0], gt[1])) / 2
            if dist < best_dist:
                best_dist = dist
                best_idx = gi

        if best_dist <= match_dist:
            if matched[best_idx]:
                red += 1   # already matched — redundant
            else:
                tp += 1
                matched[best_idx] = True
        else:
            fp += 1

    fn = sum(1 for m in matched if not m)
    return tp, fp, fn, red


# ═══════════════════════════════════════════════════════════════
# MAIN BENCHMARK
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 90)
    print("REFERENCE PIPELINE — Should reproduce F1=0.707")
    print("=" * 90)
    print()

    # Load all 23 images
    all_images = sorted(GT_LABELS.glob("*_jpg.txt"))
    print(f"Found {len(all_images)} ground-truth label files")

    results = []
    for gt_file in all_images:
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"

        if not image_path.exists():
            print(f"  SKIP {image_name}: image not found")
            continue

        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            print(f"  SKIP {image_name}: could not read image")
            continue

        h, w = gray.shape

        # Load ground truth
        gt_lines = load_ground_truth(gt_file, w, h)

        # ── PREPROCESSING ──
        # Step 1: Find HDC labels
        hdc_label = find_hdc_label(image_name, gray)

        # Step 2: Parse components
        components = parse_components(hdc_label, w, h)

        # Step 3: Occlude components
        occluded = occlude_components(gray, components)

        # Step 4: Crop to ROI
        if components:
            cropped, ox, oy = crop_to_roi(occluded, components)
        else:
            cropped, ox, oy = gray, 0, 0

        # ── DETECTION ──
        # Steps 5-10
        lines_local = detect_wires(cropped)

        # Fallback: if no lines detected, try lower k
        if not lines_local:
            # Temporarily use fallback k
            global SAUVOLA_K
            orig_k = SAUVOLA_K
            SAUVOLA_K = SAUVOLA_FALLBACK
            lines_local = detect_wires(cropped)
            SAUVOLA_K = orig_k

        # Convert to global coordinates
        lines_global = [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                        for (x1, y1), (x2, y2) in lines_local]

        # ── EVALUATE ──
        tp, fp, fn, red = evaluate(lines_global, gt_lines)

        prec = tp / max(tp + fp + red, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-8)

        results.append({
            "image": image_name,
            "gt": len(gt_lines),
            "detected": len(lines_global),
            "tp": tp, "fp": fp, "fn": fn, "red": red,
            "p": prec, "r": rec, "f1": f1,
            "comps": len(components),
            "has_hdc": hdc_label is not None,
        })

    # ── PRINT RESULTS ──
    header = f"{'Image':20s} {'GT':>3s} {'Det':>4s} {'TP':>3s} {'FP':>4s} {'FN':>3s} {'Red':>3s} {'F1':>7s} {'Comps':>5s}"
    print(f"\n{header}")
    print("-" * 80)

    tp_t = fp_t = fn_t = red_t = 0
    for r in results:
        tp_t += r["tp"]; fp_t += r["fp"]; fn_t += r["fn"]; red_t += r["red"]
        print(f"{r['image']:20s} {r['gt']:3d} {r['detected']:4d} {r['tp']:3d} "
              f"{r['fp']:4d} {r['fn']:3d} {r['red']:3d} {r['f1']:7.4f} {r['comps']:5d}")

    p = tp_t / max(tp_t + fp_t + red_t, 1)
    r_ = tp_t / max(tp_t + fn_t, 1)
    gf1 = 2 * p * r_ / max(p + r_, 1e-8)

    print(f"\n{'=' * 90}")
    print(f"GLOBAL  | F1={gf1:.4f}  TP={tp_t}  FP={fp_t}  FN={fn_t}  Red={red_t}")
    print(f"        | P={p:.4f}  R={r_:.4f}")
    print(f"Expected | F1=0.7066  TP=248  FP=70  FN=52  Red=84")
    match = "MATCH" if abs(gf1 - 0.7066) < 0.01 else f"OFF BY {abs(gf1 - 0.7066):.4f}"
    print(f"        | {match}")
    print(f"{'=' * 90}")

    # Print missing HDC images
    missing_hdc = [r for r in results if not r["has_hdc"]]
    if missing_hdc:
        print(f"\nWARNING: {len(missing_hdc)} images have NO HDC labels (no occlusion):")
        for r in missing_hdc:
            print(f"    {r['image']}")

    return results


if __name__ == "__main__":
    main()
