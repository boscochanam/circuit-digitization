from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

from wire_detection.benchmark import reference_pipeline as ref


@dataclass(slots=True)
class ExperimentConfig:
    name: str
    sauvola_k: float = 0.30
    sauvola_window: int = 51
    fallback_ks: tuple[float, ...] = (0.25,)
    close_kernel: int = 3
    ccl_min_area: int = 20
    dedup_angle: float = 10.0
    dedup_dist: float = 18.0
    crop_padding: int = 10
    occlusion_margin: float = 0.15
    normalize_mode: str = "none"
    endpoint_mode: str = "extremal"
    dual_threshold_k: float | None = None
    dedup_mode: str = "baseline"
    reconnect_enabled: bool = False
    reconnect_gap: float = 16.0
    reconnect_angle: float = 8.0
    reconnect_boundary_dist: float = 14.0
    anchor_filter_enabled: bool = False
    anchor_endpoint_dist: float = 14.0
    anchor_link_dist: float = 12.0
    secondary_recovery_enabled: bool = False
    secondary_recovery_overlap_dist: float = 10.0
    secondary_recovery_anchor_dist: float = 16.0
    secondary_recovery_link_dist: float = 12.0


@dataclass(slots=True)
class ImageResult:
    image: str
    gt: int
    detected: int
    tp: int
    fp: int
    fn: int
    red: int
    p: float
    r: float
    f1: float
    comps: int
    has_hdc: bool
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunSummary:
    config: ExperimentConfig
    global_f1: float
    precision: float
    recall: float
    tp: int
    fp: int
    fn: int
    red: int
    beat_reference: bool
    images: list[ImageResult]


def ensure_odd(value: int) -> int:
    return value if value % 2 == 1 else value + 1


def normalize_image(gray: np.ndarray, mode: str) -> np.ndarray:
    if mode == "clahe":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)
    return gray


def sauvola_binary(image: np.ndarray, k: float, window: int) -> np.ndarray:
    img_f = image.astype(np.float32)
    window = ensure_odd(max(window, 3))
    mean = cv2.boxFilter(img_f, -1, (window, window), normalize=True)
    sqr = cv2.boxFilter(img_f ** 2, -1, (window, window), normalize=True)
    std = np.sqrt(np.maximum(sqr - mean ** 2, 0))
    bw = (image > mean * (1 + k * (std / 128 - 1))).astype(np.uint8) * 255
    return cv2.bitwise_not(bw)


def build_component_mask(
    gray: np.ndarray,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    occlusion_margin: float,
) -> np.ndarray:
    h, w = gray.shape
    occluded = gray.copy()
    for _, polygon, (x1, y1, x2, y2) in components:
        margin_x = max(int((x2 - x1) * occlusion_margin), 5)
        margin_y = max(int((y2 - y1) * occlusion_margin), 5)
        sx = max(0, x1 - margin_x)
        sy = max(0, y1 - margin_y)
        ex = min(w, x2 + margin_x)
        ey = min(h, y2 + margin_y)
        fill_color = int(np.median(gray[sy:ey, sx:ex])) if (ey - sy) * (ex - sx) > 0 else 255
        cv2.fillPoly(occluded, [np.array(polygon, dtype=np.int32)], fill_color)
    return occluded


def crop_to_roi(
    image: np.ndarray,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    padding: int,
) -> tuple[np.ndarray, int, int]:
    h, w = image.shape
    if not components:
        return image, 0, 0

    x1 = min(b[0] for _, _, b in components)
    y1 = min(b[1] for _, _, b in components)
    x2 = max(b[2] for _, _, b in components)
    y2 = max(b[3] for _, _, b in components)
    rx1 = max(0, x1 - padding)
    ry1 = max(0, y1 - padding)
    rx2 = min(w, x2 + padding)
    ry2 = min(h, y2 + padding)
    return image[ry1:ry2, rx1:rx2], rx1, ry1


def shift_components(
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    ox: int,
    oy: int,
) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]]:
    shifted = []
    for cls_id, poly, (x1, y1, x2, y2) in components:
        shifted_poly = [(x - ox, y - oy) for x, y in poly]
        shifted.append((cls_id, shifted_poly, (x1 - ox, y1 - oy, x2 - ox, y2 - oy)))
    return shifted


def contour_line_extremal(cnt: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]] | None:
    pts = [
        tuple(cnt[cnt[:, :, 0].argmin()][0]),
        tuple(cnt[cnt[:, :, 0].argmax()][0]),
        tuple(cnt[cnt[:, :, 1].argmin()][0]),
        tuple(cnt[cnt[:, :, 1].argmax()][0]),
    ]
    best_dist, best_pair = -1, None
    for a in range(4):
        for b in range(a + 1, 4):
            d = (pts[a][0] - pts[b][0]) ** 2 + (pts[a][1] - pts[b][1]) ** 2
            if d > best_dist:
                best_dist = d
                best_pair = (pts[a], pts[b])
    return best_pair


def contour_line_pca(cnt: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]] | None:
    pts = cnt[:, 0, :].astype(np.float32)
    if len(pts) < 2:
        return None
    mean = np.mean(pts, axis=0)
    centered = pts - mean
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    direction = vt[0]
    proj = centered @ direction
    p1 = mean + direction * np.min(proj)
    p2 = mean + direction * np.max(proj)

    def nearest_contour(point: np.ndarray) -> tuple[int, int]:
        dists = np.sum((pts - point) ** 2, axis=1)
        nearest = pts[int(np.argmin(dists))]
        return int(nearest[0]), int(nearest[1])

    return nearest_contour(p1), nearest_contour(p2)


def extract_line_from_component(mask: np.ndarray, endpoint_mode: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    cnt = max(contours, key=cv2.contourArea)
    if endpoint_mode == "pca":
        pair = contour_line_pca(cnt)
        if pair is not None:
            return pair
    return contour_line_extremal(cnt)


def line_length(line: tuple[tuple[int, int], tuple[int, int]]) -> float:
    (x1, y1), (x2, y2) = line
    return math.hypot(x2 - x1, y2 - y1)


def line_angle(line: tuple[tuple[int, int], tuple[int, int]]) -> float:
    (x1, y1), (x2, y2) = line
    return math.atan2(y2 - y1, x2 - x1)


def angle_delta(a: float, b: float) -> float:
    delta = abs(a - b) % math.pi
    return min(delta, math.pi - delta)


def dedup_overlap(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    angle_thresh: float,
    dist_thresh: float,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if len(lines) < 2:
        return lines

    kept = sorted(lines, key=line_length, reverse=True)
    result: list[tuple[tuple[int, int], tuple[int, int]]] = []
    angle_thresh_rad = math.radians(angle_thresh)

    for candidate in kept:
        cand_angle = line_angle(candidate)
        redundant = False
        for accepted in result:
            if angle_delta(cand_angle, line_angle(accepted)) > angle_thresh_rad:
                continue
            d1 = ref._point_to_segment_dist(candidate[0], accepted[0], accepted[1])
            d2 = ref._point_to_segment_dist(candidate[1], accepted[0], accepted[1])
            overlap_like = (
                d1 <= dist_thresh
                and d2 <= dist_thresh
                and line_length(candidate) <= line_length(accepted) * 1.10
            )
            if overlap_like:
                redundant = True
                break
        if not redundant:
            result.append(candidate)
    return result


def dedup_lines(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if cfg.dedup_mode == "overlap":
        return dedup_overlap(lines, cfg.dedup_angle, cfg.dedup_dist)
    return ref._dedup(lines, angle_thresh=cfg.dedup_angle, dist_thresh=cfg.dedup_dist)


def endpoint_near_component(
    endpoint: tuple[int, int],
    bbox: tuple[int, int, int, int],
    boundary_dist: float,
) -> bool:
    x, y = endpoint
    x1, y1, x2, y2 = bbox
    if x < x1 - boundary_dist or x > x2 + boundary_dist or y < y1 - boundary_dist or y > y2 + boundary_dist:
        return False
    dx = min(abs(x - x1), abs(x - x2))
    dy = min(abs(y - y1), abs(y - y2))
    return min(dx, dy) <= boundary_dist


def line_component_anchored(
    line: tuple[tuple[int, int], tuple[int, int]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    boundary_dist: float,
) -> bool:
    return any(
        endpoint_near_component(line[0], bbox, boundary_dist) or endpoint_near_component(line[1], bbox, boundary_dist)
        for _, _, bbox in components
    )


def line_linked(
    a: tuple[tuple[int, int], tuple[int, int]],
    b: tuple[tuple[int, int], tuple[int, int]],
    dist_thresh: float,
) -> bool:
    for pt in a:
        if ref._point_to_segment_dist(pt, b[0], b[1]) <= dist_thresh:
            return True
    for pt in b:
        if ref._point_to_segment_dist(pt, a[0], a[1]) <= dist_thresh:
            return True
    return False


def filter_component_connected_lines(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not cfg.anchor_filter_enabled or not lines or not components:
        return lines

    anchored = [
        idx for idx, line in enumerate(lines)
        if line_component_anchored(line, components, cfg.anchor_endpoint_dist)
    ]
    if not anchored:
        return lines

    adjacency = {idx: set() for idx in range(len(lines))}
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            if line_linked(lines[i], lines[j], cfg.anchor_link_dist):
                adjacency[i].add(j)
                adjacency[j].add(i)

    keep = set(anchored)
    frontier = list(anchored)
    while frontier:
        node = frontier.pop()
        for nxt in adjacency[node]:
            if nxt not in keep:
                keep.add(nxt)
                frontier.append(nxt)

    return [line for idx, line in enumerate(lines) if idx in keep]


def line_overlaps_existing(
    candidate: tuple[tuple[int, int], tuple[int, int]],
    existing_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    dist_thresh: float,
) -> bool:
    for line in existing_lines:
        if (
            ref._point_to_segment_dist(candidate[0], line[0], line[1]) <= dist_thresh
            and ref._point_to_segment_dist(candidate[1], line[0], line[1]) <= dist_thresh
        ) or (
            ref._point_to_segment_dist(line[0], candidate[0], candidate[1]) <= dist_thresh
            and ref._point_to_segment_dist(line[1], candidate[0], candidate[1]) <= dist_thresh
        ):
            return True
    return False


def recovery_candidate_allowed(
    line: tuple[tuple[int, int], tuple[int, int]],
    accepted: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> bool:
    near_components = [
        endpoint_near_component(line[0], bbox, cfg.secondary_recovery_anchor_dist)
        or endpoint_near_component(line[1], bbox, cfg.secondary_recovery_anchor_dist)
        for _, _, bbox in components
    ]
    if not any(near_components):
        return False

    both_component_near = any(
        endpoint_near_component(line[0], bbox, cfg.secondary_recovery_anchor_dist)
        for _, _, bbox in components
    ) and any(
        endpoint_near_component(line[1], bbox, cfg.secondary_recovery_anchor_dist)
        for _, _, bbox in components
    )
    if both_component_near:
        return True

    for accepted_line in accepted:
        if line_linked(line, accepted_line, cfg.secondary_recovery_link_dist):
            return True
    return False


def secondary_recovery_config(cfg: ExperimentConfig) -> ExperimentConfig:
    return ExperimentConfig(
        name=f"{cfg.name}_secondary",
        sauvola_k=max(cfg.sauvola_k - 0.0025, 0.27),
        sauvola_window=51,
        fallback_ks=(),
        close_kernel=max(cfg.close_kernel, 3),
        ccl_min_area=max(20, cfg.ccl_min_area - 4),
        dedup_angle=cfg.dedup_angle,
        dedup_dist=cfg.dedup_dist,
        crop_padding=cfg.crop_padding,
        occlusion_margin=cfg.occlusion_margin,
        normalize_mode=cfg.normalize_mode,
        endpoint_mode="pca",
        dual_threshold_k=None,
        dedup_mode="overlap",
        reconnect_enabled=False,
        anchor_filter_enabled=True,
        anchor_endpoint_dist=max(cfg.anchor_endpoint_dist, cfg.secondary_recovery_anchor_dist),
        anchor_link_dist=max(cfg.anchor_link_dist, cfg.secondary_recovery_link_dist),
    )


def add_secondary_recovery_lines(
    primary_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    image: np.ndarray,
    local_components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not cfg.secondary_recovery_enabled:
        return primary_lines

    secondary_cfg = secondary_recovery_config(cfg)
    secondary_lines = detect_wires_experiment(image, local_components, secondary_cfg)
    accepted = list(primary_lines)
    for line in secondary_lines:
        if line_overlaps_existing(line, accepted, cfg.secondary_recovery_overlap_dist):
            continue
        if not recovery_candidate_allowed(line, accepted, local_components, cfg):
            continue
        accepted.append(line)

    accepted = dedup_lines(accepted, cfg)
    accepted = filter_component_connected_lines(accepted, local_components, cfg)
    return accepted


def reconnect_lines(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not cfg.reconnect_enabled or len(lines) < 2 or not components:
        return lines

    used_pairs: set[tuple[int, int]] = set()
    added: list[tuple[tuple[int, int], tuple[int, int]]] = []
    angle_thresh = math.radians(cfg.reconnect_angle)

    for comp_idx, (_, _, bbox) in enumerate(components):
        near_endpoints: list[tuple[int, int, tuple[int, int], tuple[int, int], float]] = []
        for line_idx, line in enumerate(lines):
            angle = line_angle(line)
            for endpoint_idx, endpoint in enumerate(line):
                if endpoint_near_component(endpoint, bbox, cfg.reconnect_boundary_dist):
                    far_endpoint = line[1 - endpoint_idx]
                    near_endpoints.append((line_idx, endpoint_idx, endpoint, far_endpoint, angle))

        for i in range(len(near_endpoints)):
            for j in range(i + 1, len(near_endpoints)):
                a = near_endpoints[i]
                b = near_endpoints[j]
                if a[0] == b[0] or (min(a[0], b[0]), max(a[0], b[0])) in used_pairs:
                    continue
                if angle_delta(a[4], b[4]) > angle_thresh:
                    continue
                if math.hypot(a[2][0] - b[2][0], a[2][1] - b[2][1]) > cfg.reconnect_gap:
                    continue
                candidate = (a[3], b[3])
                if line_length(candidate) < max(line_length(lines[a[0]]), line_length(lines[b[0]])):
                    continue
                used_pairs.add((min(a[0], b[0]), max(a[0], b[0])))
                added.append(candidate)

    return dedup_lines(lines + added, cfg)


def detect_wires_experiment(
    image: np.ndarray,
    local_components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    normalized = normalize_image(image, cfg.normalize_mode)
    candidate_ks = (cfg.sauvola_k,) + tuple(k for k in cfg.fallback_ks if k != cfg.sauvola_k)
    fused_lines: list[tuple[tuple[int, int], tuple[int, int]]] = []

    for idx, k in enumerate(candidate_ks):
        bw = sauvola_binary(normalized, k, cfg.sauvola_window)
        if cfg.dual_threshold_k is not None and idx == 0:
            bw_alt = sauvola_binary(normalized, cfg.dual_threshold_k, cfg.sauvola_window)
            bw = cv2.bitwise_or(bw, bw_alt)

        kernel_size = ensure_odd(max(cfg.close_kernel, 1))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)

        nlab, labels, stats, _ = cv2.connectedComponentsWithStats(closed)
        lines: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for lab_idx in range(1, nlab):
            if stats[lab_idx, cv2.CC_STAT_AREA] < cfg.ccl_min_area:
                continue
            mask = (labels == lab_idx).astype(np.uint8) * 255
            pair = extract_line_from_component(mask, cfg.endpoint_mode)
            if pair is not None:
                lines.append(pair)

        lines = dedup_lines(lines, cfg)
        lines = reconnect_lines(lines, local_components, cfg)
        lines = filter_component_connected_lines(lines, local_components, cfg)
        lines = add_secondary_recovery_lines(lines, normalized, local_components, cfg)
        if lines:
            fused_lines = lines
            break

    return fused_lines


def classify_failure(result: ImageResult) -> list[str]:
    tags: list[str] = []
    if result.f1 < 0.40:
        tags.append("hard_case")
    if result.fn >= max(4, result.gt // 3):
        tags.append("recall_heavy")
    if result.fp >= max(4, result.gt // 4):
        tags.append("fp_heavy")
    if result.red >= max(4, result.tp // 3 if result.tp else 4):
        tags.append("redundancy_heavy")
    if result.detected == 0:
        tags.append("no_detection")
    return tags


def draw_overlay(
    gray: np.ndarray,
    detected: list[tuple[tuple[int, int], tuple[int, int]]],
    ground_truth: list[tuple[tuple[int, int], tuple[int, int]]],
    out_path: Path,
) -> None:
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for (x1, y1), (x2, y2) in ground_truth:
        cv2.line(canvas, (x1, y1), (x2, y2), (0, 180, 0), 2)
    for (x1, y1), (x2, y2) in detected:
        cv2.line(canvas, (x1, y1), (x2, y2), (0, 0, 255), 2)
    cv2.imwrite(str(out_path), canvas)


def run_experiment(
    cfg: ExperimentConfig,
    output_dir: Path | None = None,
) -> RunSummary:
    results: list[ImageResult] = []
    overlay_dir = None
    if output_dir is not None:
        overlay_dir = output_dir / cfg.name / "overlays"
        overlay_dir.mkdir(parents=True, exist_ok=True)

    all_images = sorted(ref.GT_LABELS.glob("*_jpg.txt"))
    for gt_file in all_images:
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = ref.GT_IMAGES / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        hdc_label = ref.find_hdc_label(image_name, gray)
        components = ref.parse_components(hdc_label, w, h)
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        if components:
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)
        else:
            cropped, ox, oy = occluded, 0, 0
            local_components = []

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines_local]
        tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
        precision = tp / max(tp + fp + red, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)
        image_result = ImageResult(
            image=image_name,
            gt=len(gt_lines),
            detected=len(lines_global),
            tp=tp,
            fp=fp,
            fn=fn,
            red=red,
            p=precision,
            r=recall,
            f1=f1,
            comps=len(components),
            has_hdc=hdc_label is not None,
        )
        image_result.tags = classify_failure(image_result)
        results.append(image_result)
        if overlay_dir is not None:
            draw_overlay(gray, lines_global, gt_lines, overlay_dir / f"{image_name}.png")

    tp_t = sum(r.tp for r in results)
    fp_t = sum(r.fp for r in results)
    fn_t = sum(r.fn for r in results)
    red_t = sum(r.red for r in results)
    precision = tp_t / max(tp_t + fp_t + red_t, 1)
    recall = tp_t / max(tp_t + fn_t, 1)
    global_f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    summary = RunSummary(
        config=cfg,
        global_f1=global_f1,
        precision=precision,
        recall=recall,
        tp=tp_t,
        fp=fp_t,
        fn=fn_t,
        red=red_t,
        beat_reference=global_f1 > 0.7066,
        images=results,
    )
    if output_dir is not None:
        run_dir = output_dir / cfg.name
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "config": asdict(cfg),
                    "global_f1": global_f1,
                    "precision": precision,
                    "recall": recall,
                    "tp": tp_t,
                    "fp": fp_t,
                    "fn": fn_t,
                    "red": red_t,
                    "beat_reference": summary.beat_reference,
                    "images": [asdict(item) for item in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return summary


def wave1_configs() -> list[ExperimentConfig]:
    return [
        ExperimentConfig(name="baseline_control"),
        ExperimentConfig(name="clahe_fallback", normalize_mode="clahe"),
        ExperimentConfig(name="wider_window", sauvola_window=61),
        ExperimentConfig(name="k0275", sauvola_k=0.275, fallback_ks=(0.24,)),
        ExperimentConfig(name="k0285", sauvola_k=0.285, fallback_ks=(0.245,)),
        ExperimentConfig(name="dual_threshold", dual_threshold_k=0.24),
        ExperimentConfig(name="pca_endpoints", endpoint_mode="pca"),
        ExperimentConfig(name="overlap_dedup", dedup_mode="overlap"),
        ExperimentConfig(
            name="combined_safe",
            normalize_mode="clahe",
            sauvola_k=0.285,
            fallback_ks=(0.25, 0.23),
            endpoint_mode="pca",
            dedup_mode="overlap",
        ),
        ExperimentConfig(
            name="k0285_anchor_filter",
            sauvola_k=0.285,
            fallback_ks=(0.245,),
            anchor_filter_enabled=True,
        ),
    ]


def wave2_configs() -> list[ExperimentConfig]:
    return [
        ExperimentConfig(name="baseline_control"),
        ExperimentConfig(
            name="reconnect_only",
            reconnect_enabled=True,
            reconnect_gap=12.0,
            reconnect_angle=7.0,
            reconnect_boundary_dist=12.0,
        ),
        ExperimentConfig(
            name="k0275_reconnect",
            sauvola_k=0.275,
            fallback_ks=(0.24,),
            reconnect_enabled=True,
            reconnect_gap=12.0,
            reconnect_angle=7.0,
            reconnect_boundary_dist=12.0,
        ),
        ExperimentConfig(
            name="pca_overlap",
            endpoint_mode="pca",
            dedup_mode="overlap",
        ),
        ExperimentConfig(
            name="k0275_pca_overlap",
            sauvola_k=0.275,
            fallback_ks=(0.24,),
            endpoint_mode="pca",
            dedup_mode="overlap",
        ),
        ExperimentConfig(
            name="k0285_anchor_reconnect",
            sauvola_k=0.285,
            fallback_ks=(0.245,),
            reconnect_enabled=True,
            reconnect_gap=12.0,
            reconnect_angle=7.0,
            reconnect_boundary_dist=12.0,
            anchor_filter_enabled=True,
        ),
        ExperimentConfig(
            name="best_candidate_v1",
            sauvola_k=0.2875,
            fallback_ks=(),
            endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=14.0,
            anchor_link_dist=8.0,
        ),
        ExperimentConfig(
            name="best_candidate_v2",
            sauvola_k=0.285,
            sauvola_window=61,
            close_kernel=3,
            ccl_min_area=24,
            fallback_ks=(),
            endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=12.0,
            anchor_link_dist=8.0,
        ),
        ExperimentConfig(
            name="best_candidate_v3",
            sauvola_k=0.285,
            sauvola_window=61,
            close_kernel=3,
            ccl_min_area=24,
            fallback_ks=(),
            endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=12.0,
            anchor_link_dist=8.0,
            secondary_recovery_enabled=True,
            secondary_recovery_overlap_dist=10.0,
            secondary_recovery_anchor_dist=16.0,
            secondary_recovery_link_dist=10.0,
        ),
        ExperimentConfig(
            name="best_candidate_v4",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            ccl_min_area=28,
            fallback_ks=(),
            endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=12.0,
            anchor_link_dist=8.0,
        ),
    ]


def save_ranking(summaries: list[RunSummary], output_dir: Path, preset_name: str) -> None:
    ranking = sorted(summaries, key=lambda item: item.global_f1, reverse=True)
    data = [
        {
            "name": summary.config.name,
            "global_f1": summary.global_f1,
            "precision": summary.precision,
            "recall": summary.recall,
            "tp": summary.tp,
            "fp": summary.fp,
            "fn": summary.fn,
            "red": summary.red,
            "beat_reference": summary.beat_reference,
            "config": asdict(summary.config),
        }
        for summary in ranking
    ]
    (output_dir / f"{preset_name}_ranking.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "| name | global_f1 | precision | recall | tp | fp | fn | red | beat_reference |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in data:
        lines.append(
            f"| {row['name']} | {row['global_f1']:.4f} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {row['red']} | {'yes' if row['beat_reference'] else 'no'} |"
        )
    (output_dir / f"{preset_name}_ranking.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark experiments against the frozen reference pipeline.")
    parser.add_argument("--preset", choices=["wave1", "wave2"], default="wave1")
    parser.add_argument("--output-dir", type=Path, default=Path("output/benchmark_experiments"))
    args = parser.parse_args()

    configs = wave1_configs() if args.preset == "wave1" else wave2_configs()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = [run_experiment(cfg, args.output_dir) for cfg in configs]
    save_ranking(summaries, args.output_dir, args.preset)

    ranking = sorted(summaries, key=lambda item: item.global_f1, reverse=True)
    print("name\tf1\tprecision\trecall\ttp\tfp\tfn\tred")
    for item in ranking:
        print(
            f"{item.config.name}\t{item.global_f1:.4f}\t{item.precision:.4f}\t{item.recall:.4f}\t"
            f"{item.tp}\t{item.fp}\t{item.fn}\t{item.red}"
        )


if __name__ == "__main__":
    main()
