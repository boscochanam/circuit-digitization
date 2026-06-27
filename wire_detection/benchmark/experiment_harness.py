from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.sdg.generator import SDG, SDGConfig


@dataclass(slots=True)
class ExperimentConfig:
    name: str
    threshold_method: str = "sauvola"
    extra_threshold_methods: tuple[str, ...] = ()
    sauvola_k: float = 0.30
    sauvola_window: int = 51
    fallback_ks: tuple[float, ...] = (0.25,)
    threshold_block_size: int = 51
    threshold_c: float = 12.0
    threshold_blur: int = 3
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
    secondary_threshold_method: str | None = None
    secondary_extra_threshold_methods: tuple[str, ...] = ()
    secondary_threshold_block_size: int | None = None
    secondary_threshold_c: float | None = None
    secondary_threshold_blur: int | None = None
    secondary_topology_filter_enabled: bool = False
    secondary_recovery_overlap_dist: float = 10.0
    secondary_recovery_anchor_dist: float = 16.0
    secondary_recovery_link_dist: float = 12.0
    secondary_require_both_anchors: bool = False
    secondary_parallel_reject_enabled: bool = False
    secondary_parallel_angle: float = 7.0
    secondary_parallel_dist: float = 10.0
    secondary_endpoint_novelty_radius: float = 10.0
    secondary_topology_driven: bool = False
    secondary_endpoint_seed_radius: float = 8.0
    secondary_endpoint_target_radius: float = 10.0
    secondary_max_repairs_per_seed: int = 1
    stroke_repair_enabled: bool = False
    stroke_repair_seed_radius: float = 8.0
    stroke_repair_target_radius: float = 12.0
    stroke_repair_max_gap: float = 42.0
    stroke_repair_support_min: float = 1.18
    stroke_repair_darkness_min: float = 0.57
    stroke_repair_max_per_seed: int = 1
    class_port_gating_enabled: bool = False
    recovery_complexity_gate_enabled: bool = False
    recovery_utility_min: float = 1.0
    extraction_mode: str = "component"
    threshold_fusion_enabled: bool = False
    threshold_vote: int = 1
    threshold_union_with_clahe: bool = False
    graph_min_path_len: float = 16.0
    graph_anchor_bonus: float = 0.35
    graph_support_bonus: float = 0.6
    graph_cluster_dist: float = 12.0
    graph_port_dist: float = 18.0
    topology_filter_enabled: bool = False
    topology_endpoint_radius: float = 12.0
    topology_support_min: float = 1.1
    topology_overlap_dist: float = 10.0
    hough_enabled: bool = False
    hough_threshold: int = 18
    hough_min_line_length: int = 18
    hough_max_line_gap: int = 6
    endpoint_snap_enabled: bool = False
    endpoint_snap_dist: float = 14.0


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
    synthetic_f1: float = 0.0
    synthetic_precision: float = 0.0
    synthetic_recall: float = 0.0
    synthetic_tp: int = 0
    synthetic_fp: int = 0
    synthetic_fn: int = 0
    synthetic_red: int = 0


@dataclass(slots=True)
class CandidateLine:
    line: tuple[tuple[int, int], tuple[int, int]]
    score: float
    support: float
    anchor_count: int
    source: str


HDC_CLASS_NAMES = [
    "text", "junction", "crossover", "terminal", "gnd", "vss", "voltage-dc", "voltage-ac",
    "voltage-battery", "resistor", "resistor-adjustable", "resistor-photo",
    "capacitor-unpolarized", "capacitor-polarized", "capacitor-adjustable", "inductor",
    "inductor-ferrite", "transformer", "diode", "diode-light_emitting", "diode-thyrector",
    "diode-zener", "diac", "triac", "thyristor", "varistor", "transistor-bjt",
    "transistor-fet", "transistor-photo", "operational_amplifier",
    "operational_amplifier-schmitt_trigger", "optocoupler", "integrated_circuit",
    "integrated_circuit-ne555", "integrated_circuit-voltage_regulator", "xor", "and", "or",
    "not", "nand", "nor", "probe", "probe-current", "probe-voltage", "switch", "relay",
    "socket", "fuse", "speaker", "motor", "lamp", "microphone", "antenna", "crystal",
    "mechanical", "magnetic", "optical", "unknown",
]

NON_CONNECTIVE_CLASSES = {"text", "junction", "crossover", "unknown"}
TWO_TERMINAL_CLASSES = {
    "resistor", "resistor-adjustable", "resistor-photo", "capacitor-unpolarized",
    "capacitor-polarized", "capacitor-adjustable", "inductor", "inductor-ferrite",
    "diode", "diode-light_emitting", "diode-thyrector", "diode-zener", "diac", "triac",
    "thyristor", "varistor", "switch", "fuse", "lamp", "crystal", "voltage-dc",
    "voltage-ac", "voltage-battery", "probe", "probe-current", "probe-voltage",
}


def ensure_odd(value: int) -> int:
    return value if value % 2 == 1 else value + 1


def normalize_image(gray: np.ndarray, mode: str) -> np.ndarray:
    if mode in {"clahe", "local_contrast"}:
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


def blur_for_threshold(image: np.ndarray, blur_size: int) -> np.ndarray:
    blur_size = max(int(blur_size), 0)
    if blur_size <= 1:
        return image
    blur_size = ensure_odd(blur_size)
    return cv2.GaussianBlur(image, (blur_size, blur_size), 0)


def otsu_binary(image: np.ndarray, blur_size: int) -> np.ndarray:
    source = blur_for_threshold(image, blur_size)
    _, bw = cv2.threshold(source, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return bw


def triangle_binary(image: np.ndarray, blur_size: int) -> np.ndarray:
    source = blur_for_threshold(image, blur_size)
    _, bw = cv2.threshold(source, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_TRIANGLE)
    return bw


def adaptive_binary(image: np.ndarray, method: str, block_size: int, c_value: float) -> np.ndarray:
    block_size = ensure_odd(max(int(block_size), 3))
    adaptive_method = cv2.ADAPTIVE_THRESH_MEAN_C if method == "adaptive_mean" else cv2.ADAPTIVE_THRESH_GAUSSIAN_C
    return cv2.adaptiveThreshold(
        image,
        255,
        adaptive_method,
        cv2.THRESH_BINARY_INV,
        block_size,
        float(c_value),
    )


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


def component_side_midpoints(bbox: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    return [(cx, y1), (cx, y2), (x1, cy), (x2, cy)]


def class_name_for_id(cls_id: int) -> str:
    if 0 <= cls_id < len(HDC_CLASS_NAMES):
        return HDC_CLASS_NAMES[cls_id]
    return "unknown"


def polygon_edge_midpoints(polygon: list[tuple[int, int]]) -> list[tuple[tuple[int, int], float]]:
    if len(polygon) != 4:
        return []
    midpoints: list[tuple[tuple[int, int], float]] = []
    for idx in range(4):
        p1 = polygon[idx]
        p2 = polygon[(idx + 1) % 4]
        midpoint = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        midpoints.append((midpoint, length))
    return midpoints


def candidate_component_ports(
    cls_id: int,
    polygon: list[tuple[int, int]],
    bbox: tuple[int, int, int, int],
    cfg: ExperimentConfig,
) -> list[tuple[int, int]]:
    name = class_name_for_id(cls_id)
    if cfg.class_port_gating_enabled and name in NON_CONNECTIVE_CLASSES:
        return []
    if not cfg.class_port_gating_enabled:
        return component_side_midpoints(bbox)
    edge_midpoints = polygon_edge_midpoints(polygon)
    if name in TWO_TERMINAL_CLASSES and len(edge_midpoints) == 4:
        ordered = sorted(edge_midpoints, key=lambda item: item[1])
        return [ordered[0][0], ordered[1][0]]
    if edge_midpoints:
        return [item[0] for item in edge_midpoints]
    return component_side_midpoints(bbox)


def nearest_component_port(
    endpoint: tuple[int, int],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig | None = None,
) -> tuple[tuple[int, int] | None, float]:
    best_pt = None
    best = float("inf")
    effective_cfg = cfg or ExperimentConfig(name="port_helper")
    for cls_id, polygon, bbox in components:
        for port in candidate_component_ports(cls_id, polygon, bbox, effective_cfg):
            d = math.hypot(endpoint[0] - port[0], endpoint[1] - port[1])
            if d < best:
                best = d
                best_pt = port
    return best_pt, best


def endpoint_port_distance(
    endpoint: tuple[int, int],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig | None = None,
) -> float:
    best = float("inf")
    effective_cfg = cfg or ExperimentConfig(name="port_helper")
    for cls_id, polygon, bbox in components:
        for port in candidate_component_ports(cls_id, polygon, bbox, effective_cfg):
            best = min(best, math.hypot(endpoint[0] - port[0], endpoint[1] - port[1]))
    return best


def line_component_anchored(
    line: tuple[tuple[int, int], tuple[int, int]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    boundary_dist: float,
    cfg: ExperimentConfig | None = None,
) -> bool:
    effective_cfg = cfg or ExperimentConfig(name="anchor_helper")
    for endpoint in line:
        for cls_id, polygon, bbox in components:
            ports = candidate_component_ports(cls_id, polygon, bbox, effective_cfg)
            if ports:
                if any(math.hypot(endpoint[0] - px, endpoint[1] - py) <= boundary_dist for px, py in ports):
                    return True
            elif endpoint_near_component(endpoint, bbox, boundary_dist):
                return True
    return False


def count_line_anchors(
    line: tuple[tuple[int, int], tuple[int, int]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    boundary_dist: float,
    cfg: ExperimentConfig | None = None,
) -> int:
    effective_cfg = cfg or ExperimentConfig(name="anchor_count_helper")
    count = 0
    for endpoint in line:
        anchored = False
        for cls_id, polygon, bbox in components:
            ports = candidate_component_ports(cls_id, polygon, bbox, effective_cfg)
            if ports:
                if any(math.hypot(endpoint[0] - px, endpoint[1] - py) <= boundary_dist for px, py in ports):
                    anchored = True
                    break
            elif endpoint_near_component(endpoint, bbox, boundary_dist):
                anchored = True
                break
        if anchored:
            count += 1
    return count


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
        if line_component_anchored(line, components, cfg.anchor_endpoint_dist, cfg)
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


def count_endpoint_neighbors(
    endpoint: tuple[int, int],
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    radius: float,
) -> int:
    count = 0
    for line in lines:
        for pt in line:
            if math.hypot(endpoint[0] - pt[0], endpoint[1] - pt[1]) <= radius:
                count += 1
    return count


def accepted_graph_endpoints(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    radius: float,
) -> list[tuple[int, int]]:
    endpoints: list[tuple[int, int]] = []
    for line in lines:
        for endpoint in line:
            if count_endpoint_neighbors(endpoint, lines, radius) <= 1:
                endpoints.append(endpoint)
    return endpoints


def endpoint_near_any(
    endpoint: tuple[int, int],
    points: list[tuple[int, int]],
    radius: float,
) -> bool:
    return any(math.hypot(endpoint[0] - px, endpoint[1] - py) <= radius for px, py in points)


def line_parallel_to_existing(
    candidate: tuple[tuple[int, int], tuple[int, int]],
    accepted: list[tuple[tuple[int, int], tuple[int, int]]],
    angle_thresh_deg: float,
    dist_thresh: float,
) -> bool:
    angle_thresh = math.radians(angle_thresh_deg)
    cand_angle = line_angle(candidate)
    for line in accepted:
        if angle_delta(cand_angle, line_angle(line)) > angle_thresh:
            continue
        d1 = ref._point_to_segment_dist(candidate[0], line[0], line[1])
        d2 = ref._point_to_segment_dist(candidate[1], line[0], line[1])
        if d1 <= dist_thresh and d2 <= dist_thresh:
            return True
    return False


def endpoint_seed_matches(
    line: tuple[tuple[int, int], tuple[int, int]],
    unresolved: list[tuple[int, int]],
    seed_radius: float,
) -> list[int]:
    return [
        idx
        for idx, endpoint in enumerate(line)
        if endpoint_near_any(endpoint, unresolved, seed_radius)
    ]


def endpoint_target_matches(
    endpoint: tuple[int, int],
    unresolved: list[tuple[int, int]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> bool:
    if endpoint_near_any(endpoint, unresolved, cfg.secondary_endpoint_target_radius):
        return True
    return count_line_anchors((endpoint, endpoint), components, cfg.secondary_recovery_anchor_dist, cfg) > 0


def recovery_graph_utility(
    line: tuple[tuple[int, int], tuple[int, int]],
    accepted: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> float:
    unresolved = accepted_graph_endpoints(accepted, cfg.secondary_endpoint_novelty_radius)
    unresolved_hits = sum(
        1 for endpoint in line if endpoint_near_any(endpoint, unresolved, cfg.secondary_recovery_link_dist)
    )
    anchor_hits = count_line_anchors(line, components, cfg.secondary_recovery_anchor_dist, cfg)
    novel_endpoints = sum(
        1
        for endpoint in line
        if not endpoint_near_any(endpoint, unresolved, cfg.secondary_recovery_link_dist)
        and count_line_anchors((endpoint, endpoint), components, cfg.secondary_recovery_anchor_dist, cfg) == 0
    )
    utility = float(unresolved_hits) + 0.75 * float(anchor_hits) - 1.25 * float(novel_endpoints)
    if line_parallel_to_existing(line, accepted, cfg.secondary_parallel_angle, cfg.secondary_parallel_dist):
        utility -= 0.75
    return utility


def recovery_candidate_allowed(
    line: tuple[tuple[int, int], tuple[int, int]],
    accepted: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> bool:
    unresolved = accepted_graph_endpoints(accepted, cfg.secondary_endpoint_novelty_radius)

    if cfg.secondary_topology_driven:
        seed_matches = endpoint_seed_matches(line, unresolved, cfg.secondary_endpoint_seed_radius)
        if not seed_matches:
            return False
        other_indices = [1 - idx for idx in seed_matches]
        if not any(
            endpoint_target_matches(line[other_idx], unresolved, components, cfg)
            for other_idx in other_indices
        ):
            return False

    if cfg.recovery_complexity_gate_enabled:
        if recovery_graph_utility(line, accepted, components, cfg) < cfg.recovery_utility_min:
            return False

    endpoint_anchor_flags = [
        count_line_anchors((endpoint, endpoint), components, cfg.secondary_recovery_anchor_dist, cfg) > 0
        for endpoint in line
    ]
    anchor_count = sum(endpoint_anchor_flags)
    if anchor_count == 0:
        return False

    if cfg.secondary_require_both_anchors and anchor_count < 2:
        return False

    endpoint_graph_flags = [
        endpoint_near_any(endpoint, unresolved, cfg.secondary_recovery_link_dist)
        for endpoint in line
    ]

    if anchor_count >= 2:
        return True

    if cfg.secondary_parallel_reject_enabled and line_parallel_to_existing(
        line,
        accepted,
        cfg.secondary_parallel_angle,
        cfg.secondary_parallel_dist,
    ):
        if not any(endpoint_graph_flags):
            return False

    if anchor_count == 1 and any(endpoint_graph_flags):
        return True

    for accepted_line in accepted:
        if line_linked(line, accepted_line, cfg.secondary_recovery_link_dist) and any(endpoint_graph_flags):
            return True
    return False


def secondary_recovery_config(cfg: ExperimentConfig) -> ExperimentConfig:
    return ExperimentConfig(
        name=f"{cfg.name}_secondary",
        threshold_method=cfg.secondary_threshold_method or cfg.threshold_method,
        extra_threshold_methods=cfg.secondary_extra_threshold_methods,
        sauvola_k=max(cfg.sauvola_k - 0.0025, 0.27),
        sauvola_window=51,
        fallback_ks=(),
        threshold_block_size=cfg.secondary_threshold_block_size or cfg.threshold_block_size,
        threshold_c=cfg.secondary_threshold_c if cfg.secondary_threshold_c is not None else cfg.threshold_c,
        threshold_blur=cfg.secondary_threshold_blur or cfg.threshold_blur,
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
        extraction_mode=cfg.extraction_mode,
        threshold_fusion_enabled=cfg.threshold_fusion_enabled,
        threshold_vote=cfg.threshold_vote,
        threshold_union_with_clahe=cfg.threshold_union_with_clahe,
        graph_min_path_len=cfg.graph_min_path_len,
        graph_anchor_bonus=cfg.graph_anchor_bonus,
        graph_support_bonus=cfg.graph_support_bonus,
        graph_cluster_dist=cfg.graph_cluster_dist,
        graph_port_dist=cfg.graph_port_dist,
        topology_filter_enabled=cfg.secondary_topology_filter_enabled,
        topology_endpoint_radius=cfg.topology_endpoint_radius,
        topology_support_min=cfg.topology_support_min,
        topology_overlap_dist=cfg.topology_overlap_dist,
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
    unresolved = accepted_graph_endpoints(accepted, cfg.secondary_endpoint_novelty_radius)
    accepted_by_seed: dict[int, int] = {idx: 0 for idx in range(len(unresolved))}

    def candidate_seed_ids(
        candidate: tuple[tuple[int, int], tuple[int, int]],
    ) -> list[int]:
        if not cfg.secondary_topology_driven:
            return []
        seed_ids: list[int] = []
        for seed_idx, unresolved_endpoint in enumerate(unresolved):
            if any(
                math.hypot(endpoint[0] - unresolved_endpoint[0], endpoint[1] - unresolved_endpoint[1])
                <= cfg.secondary_endpoint_seed_radius
                for endpoint in candidate
            ):
                seed_ids.append(seed_idx)
        return seed_ids

    ordered_secondary = sorted(
        secondary_lines,
        key=lambda line: candidate_line_score(line, cfg, local_components, source="recovery").score,
        reverse=True,
    )

    for line in ordered_secondary:
        if line_overlaps_existing(line, accepted, cfg.secondary_recovery_overlap_dist):
            continue
        seed_ids = candidate_seed_ids(line)
        if cfg.secondary_topology_driven:
            if not seed_ids:
                continue
            if all(
                accepted_by_seed.get(seed_idx, 0) >= cfg.secondary_max_repairs_per_seed
                for seed_idx in seed_ids
            ):
                continue
        if not recovery_candidate_allowed(line, accepted, local_components, cfg):
            continue
        accepted.append(line)
        for seed_idx in seed_ids:
            accepted_by_seed[seed_idx] = accepted_by_seed.get(seed_idx, 0) + 1

    accepted = dedup_lines(accepted, cfg, local_components)
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

    for _, _, bbox in components:
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

    return dedup_lines(lines + added, cfg, components)


def candidate_line_score(
    line: tuple[tuple[int, int], tuple[int, int]],
    cfg: ExperimentConfig,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]] | None = None,
    support_map: np.ndarray | None = None,
    source: str = "component",
) -> CandidateLine:
    components = components or []
    length = line_length(line)
    anchor_count = count_line_anchors(line, components, cfg.anchor_endpoint_dist, cfg) if components else 0
    port_d1 = endpoint_port_distance(line[0], components, cfg) if components else float("inf")
    port_d2 = endpoint_port_distance(line[1], components, cfg) if components else float("inf")
    port_bonus = 0.0
    if min(port_d1, port_d2) <= cfg.graph_port_dist:
        port_bonus += 0.2
    if max(port_d1, port_d2) <= cfg.graph_port_dist * 1.4:
        port_bonus += 0.15

    support = 1.0
    if support_map is not None:
        num = max(int(length), 2)
        xs = np.linspace(line[0][0], line[1][0], num=num)
        ys = np.linspace(line[0][1], line[1][1], num=num)
        samples = []
        h, w = support_map.shape
        for x, y in zip(xs, ys):
            xi = int(round(x))
            yi = int(round(y))
            if 0 <= xi < w and 0 <= yi < h:
                samples.append(float(support_map[yi, xi]))
        if samples:
            support = float(np.mean(samples))

    score = length
    score *= 1.0 + cfg.graph_support_bonus * max(support - 1.0, 0.0)
    score *= 1.0 + cfg.graph_anchor_bonus * anchor_count
    score *= 1.0 + port_bonus
    return CandidateLine(line=line, score=score, support=support, anchor_count=anchor_count, source=source)


def sample_line_values(
    line: tuple[tuple[int, int], tuple[int, int]],
    image: np.ndarray,
) -> list[float]:
    length = max(int(round(line_length(line))), 2)
    xs = np.linspace(line[0][0], line[1][0], num=length)
    ys = np.linspace(line[0][1], line[1][1], num=length)
    h, w = image.shape[:2]
    samples: list[float] = []
    for x, y in zip(xs, ys):
        xi = int(round(x))
        yi = int(round(y))
        if 0 <= xi < w and 0 <= yi < h:
            samples.append(float(image[yi, xi]))
    return samples


def line_darkness_score(
    line: tuple[tuple[int, int], tuple[int, int]],
    gray: np.ndarray,
) -> float:
    samples = sample_line_values(line, gray)
    if not samples:
        return 0.0
    return float(np.mean([(255.0 - v) / 255.0 for v in samples]))


def line_support_score(
    line: tuple[tuple[int, int], tuple[int, int]],
    support_map: np.ndarray,
) -> float:
    samples = sample_line_values(line, support_map)
    if not samples:
        return 0.0
    return float(np.mean(samples))


def dedup_by_score_cluster(
    candidates: list[CandidateLine],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not candidates:
        return []
    angle_thresh_rad = math.radians(cfg.dedup_angle)
    ordered = sorted(candidates, key=lambda c: (c.score, line_length(c.line)), reverse=True)
    kept: list[CandidateLine] = []
    for cand in ordered:
        redundant = False
        for accepted in kept:
            if angle_delta(line_angle(cand.line), line_angle(accepted.line)) > angle_thresh_rad:
                continue
            d1 = ref._point_to_segment_dist(cand.line[0], accepted.line[0], accepted.line[1])
            d2 = ref._point_to_segment_dist(cand.line[1], accepted.line[0], accepted.line[1])
            reverse_d1 = ref._point_to_segment_dist(accepted.line[0], cand.line[0], cand.line[1])
            reverse_d2 = ref._point_to_segment_dist(accepted.line[1], cand.line[0], cand.line[1])
            if (
                d1 <= cfg.graph_cluster_dist and d2 <= cfg.graph_cluster_dist
            ) or (
                reverse_d1 <= cfg.graph_cluster_dist and reverse_d2 <= cfg.graph_cluster_dist
            ):
                redundant = True
                break
        if not redundant:
            kept.append(cand)
    return [c.line for c in kept]


def line_intersects_selected_topology(
    line: tuple[tuple[int, int], tuple[int, int]],
    selected: list[tuple[tuple[int, int], tuple[int, int]]],
    dist_thresh: float,
) -> bool:
    for accepted in selected:
        if line_overlaps_existing(line, [accepted], dist_thresh):
            return True
    return False


def endpoint_novelty(
    endpoint: tuple[int, int],
    selected: list[tuple[tuple[int, int], tuple[int, int]]],
    radius: float,
) -> bool:
    for line in selected:
        for existing in line:
            if math.hypot(endpoint[0] - existing[0], endpoint[1] - existing[1]) <= radius:
                return False
    return True


def topology_select_lines(
    candidates: list[CandidateLine],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not cfg.topology_filter_enabled or not candidates:
        return [c.line for c in candidates]

    ordered = sorted(candidates, key=lambda c: (c.score, line_length(c.line)), reverse=True)
    selected: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for cand in ordered:
        line = cand.line
        if line_intersects_selected_topology(line, selected, cfg.topology_overlap_dist):
            continue

        novel_endpoints = sum(
            1 for endpoint in line if endpoint_novelty(endpoint, selected, cfg.topology_endpoint_radius)
        )
        linked_to_graph = any(line_linked(line, accepted, cfg.anchor_link_dist) for accepted in selected)
        anchored = cand.anchor_count > 0
        strong_support = cand.support >= cfg.topology_support_min

        if not selected:
            if anchored or strong_support:
                selected.append(line)
            continue

        if anchored and (novel_endpoints > 0 or linked_to_graph):
            selected.append(line)
            continue

        if cand.anchor_count >= 2 and strong_support:
            selected.append(line)
            continue

        if linked_to_graph and strong_support and novel_endpoints > 0:
            selected.append(line)
            continue

        # Keep only very strong unanchored paths if they extend the current explanation.
        if not anchored and linked_to_graph and cand.support >= (cfg.topology_support_min + 0.35) and novel_endpoints > 0:
            selected.append(line)

    return selected


def add_stroke_repairs(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    gray: np.ndarray,
    support_map: np.ndarray,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not cfg.stroke_repair_enabled or not lines or not components:
        return lines

    unresolved = accepted_graph_endpoints(lines, cfg.secondary_endpoint_novelty_radius)
    if not unresolved:
        return lines

    accepted = list(lines)
    repairs_by_seed: dict[int, int] = {idx: 0 for idx in range(len(unresolved))}
    port_points = [port for _, _, bbox in components for port in component_side_midpoints(bbox)]

    for seed_idx, seed in enumerate(unresolved):
        if repairs_by_seed[seed_idx] >= cfg.stroke_repair_max_per_seed:
            continue

        local_candidates: list[CandidateLine] = []
        targets: list[tuple[int, int]] = []
        for other_idx, other in enumerate(unresolved):
            if other_idx == seed_idx:
                continue
            gap = math.hypot(seed[0] - other[0], seed[1] - other[1])
            if cfg.stroke_repair_seed_radius <= gap <= cfg.stroke_repair_max_gap:
                targets.append(other)
        for port in port_points:
            gap = math.hypot(seed[0] - port[0], seed[1] - port[1])
            if gap <= cfg.stroke_repair_max_gap:
                targets.append(port)

        for target in targets:
            line = (seed, target)
            if line_overlaps_existing(line, accepted, cfg.secondary_recovery_overlap_dist):
                continue
            if line_parallel_to_existing(line, accepted, cfg.secondary_parallel_angle, cfg.secondary_parallel_dist):
                continue
            if count_line_anchors(line, components, cfg.secondary_recovery_anchor_dist) == 0:
                continue
            support = line_support_score(line, support_map)
            darkness = line_darkness_score(line, gray)
            if support < cfg.stroke_repair_support_min or darkness < cfg.stroke_repair_darkness_min:
                continue
            cand = candidate_line_score(line, cfg, components, support_map, source="stroke_repair")
            local_candidates.append(
                CandidateLine(
                    line=cand.line,
                    score=cand.score * (1.0 + 0.25 * darkness),
                    support=cand.support,
                    anchor_count=cand.anchor_count,
                    source=cand.source,
                )
            )

        local_candidates.sort(key=lambda c: c.score, reverse=True)
        for cand in local_candidates[: cfg.stroke_repair_max_per_seed]:
            accepted.append(cand.line)
            repairs_by_seed[seed_idx] += 1

    if len(accepted) == len(lines):
        return lines

    rescored = [candidate_line_score(line, cfg, components, support_map, source="mixed") for line in accepted]
    selected = topology_select_lines(rescored, components, cfg)
    selected = dedup_lines(selected, cfg, components, support_map)
    selected = filter_component_connected_lines(selected, components, cfg)
    return selected


def snap_line_endpoints(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if not cfg.endpoint_snap_enabled or not components:
        return lines
    snapped: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for line in lines:
        new_pts = []
        for endpoint in line:
            port, dist = nearest_component_port(endpoint, components)
            if port is not None and dist <= cfg.endpoint_snap_dist:
                new_pts.append(port)
            else:
                new_pts.append(endpoint)
        snapped.append((new_pts[0], new_pts[1]))
    return snapped


def dedup_lines(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    cfg: ExperimentConfig,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]] | None = None,
    support_map: np.ndarray | None = None,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if cfg.dedup_mode == "overlap":
        return dedup_overlap(lines, cfg.dedup_angle, cfg.dedup_dist)
    if cfg.dedup_mode == "score_cluster":
        candidates = [candidate_line_score(line, cfg, components, support_map) for line in lines]
        return dedup_by_score_cluster(candidates, cfg)
    return ref._dedup(lines, angle_thresh=cfg.dedup_angle, dist_thresh=cfg.dedup_dist)


def build_binary_masks(image: np.ndarray, cfg: ExperimentConfig) -> list[np.ndarray]:
    threshold_methods = [cfg.threshold_method]
    for method in cfg.extra_threshold_methods:
        if method not in threshold_methods:
            threshold_methods.append(method)
    sources = [image]
    if cfg.threshold_union_with_clahe:
        sources.append(normalize_image(image, "clahe"))

    masks: list[np.ndarray] = []
    kernel_size = ensure_odd(max(cfg.close_kernel, 1))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    for source in sources:
        for method in threshold_methods:
            binaries: list[np.ndarray] = []
            if method == "sauvola":
                candidate_ks = [cfg.sauvola_k]
                if cfg.dual_threshold_k is not None:
                    candidate_ks.append(cfg.dual_threshold_k)
                for k in cfg.fallback_ks:
                    if k not in candidate_ks:
                        candidate_ks.append(k)
                binaries = [sauvola_binary(source, k, cfg.sauvola_window) for k in candidate_ks]
            elif method == "otsu":
                binaries = [otsu_binary(source, cfg.threshold_blur)]
            elif method == "triangle":
                binaries = [triangle_binary(source, cfg.threshold_blur)]
            elif method in {"adaptive_mean", "adaptive_gaussian"}:
                binaries = [adaptive_binary(source, method, cfg.threshold_block_size, cfg.threshold_c)]
            else:
                raise ValueError(f"Unsupported threshold method: {method}")

            for bw in binaries:
                closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)
                masks.append(closed)
    return masks


def fuse_masks(masks: list[np.ndarray], vote: int) -> tuple[np.ndarray, np.ndarray]:
    if not masks:
        raise ValueError("At least one mask is required")
    stack = np.stack([(m > 0).astype(np.uint8) for m in masks], axis=0)
    support = np.sum(stack, axis=0).astype(np.float32)
    fused = (support >= max(vote, 1)).astype(np.uint8) * 255
    return fused, support


def skeleton_neighbors(skel: np.ndarray, y: int, x: int) -> list[tuple[int, int]]:
    h, w = skel.shape
    neigh: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            ny = y + dy
            nx = x + dx
            if 0 <= ny < h and 0 <= nx < w and skel[ny, nx]:
                neigh.append((ny, nx))
    return neigh


def trace_skeleton_paths(skel: np.ndarray) -> list[list[tuple[int, int]]]:
    coords = np.argwhere(skel > 0)
    if len(coords) == 0:
        return []
    degree: dict[tuple[int, int], int] = {}
    nodes: set[tuple[int, int]] = set()
    for y, x in coords:
        key = (int(y), int(x))
        deg = len(skeleton_neighbors(skel, key[0], key[1]))
        degree[key] = deg
        if deg != 2:
            nodes.add(key)
    if not nodes:
        nodes.add(tuple(map(int, coords[0])))

    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    paths: list[list[tuple[int, int]]] = []
    for node in nodes:
        for nb in skeleton_neighbors(skel, node[0], node[1]):
            edge = tuple(sorted((node, nb)))
            if edge in visited_edges:
                continue
            path = [node]
            prev = node
            cur = nb
            visited_edges.add(edge)
            while True:
                path.append(cur)
                if cur in nodes and cur != node:
                    break
                next_neighbors = [n for n in skeleton_neighbors(skel, cur[0], cur[1]) if n != prev]
                if not next_neighbors:
                    break
                nxt = next_neighbors[0]
                edge = tuple(sorted((cur, nxt)))
                if edge in visited_edges:
                    break
                visited_edges.add(edge)
                prev, cur = cur, nxt
            if len(path) >= 2:
                paths.append(path)
    return paths


def fit_line_to_path(path: list[tuple[int, int]]) -> tuple[tuple[int, int], tuple[int, int]]:
    start = path[0]
    end = path[-1]
    return (start[1], start[0]), (end[1], end[0])


def extract_lines_from_skeleton(
    fused_mask: np.ndarray,
    support_map: np.ndarray,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    skel = skeletonize((fused_mask > 0).astype(bool)).astype(np.uint8)
    paths = trace_skeleton_paths(skel)
    candidates: list[CandidateLine] = []
    for path in paths:
        line = fit_line_to_path(path)
        if line_length(line) < cfg.graph_min_path_len:
            continue
        candidate = candidate_line_score(line, cfg, components, support_map, source="skeleton")
        if candidate.anchor_count == 0 and candidate.support < 1.25 and line_length(line) < cfg.graph_min_path_len * 1.8:
            continue
        candidates.append(candidate)
    candidates = [
        CandidateLine(
            line=c.line,
            score=c.score,
            support=c.support,
            anchor_count=c.anchor_count,
            source=c.source,
        )
        for c in candidates
    ]
    topo_lines = topology_select_lines(candidates, components, cfg)
    if cfg.topology_filter_enabled:
        candidates = [c for c in candidates if c.line in topo_lines]
    if cfg.dedup_mode == "score_cluster":
        return dedup_by_score_cluster(candidates, cfg)
    lines = [c.line for c in sorted(candidates, key=lambda c: c.score, reverse=True)]
    return dedup_lines(lines, cfg, components, support_map)


def extract_lines_from_hough(
    fused_mask: np.ndarray,
    support_map: np.ndarray,
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[CandidateLine]:
    if not cfg.hough_enabled:
        return []
    raw = cv2.HoughLinesP(
        fused_mask,
        rho=1,
        theta=np.pi / 180.0,
        threshold=cfg.hough_threshold,
        minLineLength=cfg.hough_min_line_length,
        maxLineGap=cfg.hough_max_line_gap,
    )
    if raw is None:
        return []
    candidates: list[CandidateLine] = []
    for arr in raw:
        x1, y1, x2, y2 = map(int, arr[0])
        line = ((x1, y1), (x2, y2))
        if line_length(line) < cfg.graph_min_path_len:
            continue
        cand = candidate_line_score(line, cfg, components, support_map, source="hough")
        if cand.anchor_count == 0 and cand.support < 1.2:
            continue
        candidates.append(cand)
    return candidates


def extract_lines_from_components(
    masks: list[np.ndarray],
    local_components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    fused_lines: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for closed in masks:
        nlab, labels, stats, _ = cv2.connectedComponentsWithStats(closed)
        lines: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for lab_idx in range(1, nlab):
            if stats[lab_idx, cv2.CC_STAT_AREA] < cfg.ccl_min_area:
                continue
            mask = (labels == lab_idx).astype(np.uint8) * 255
            pair = extract_line_from_component(mask, cfg.endpoint_mode)
            if pair is not None:
                lines.append(pair)
        lines = dedup_lines(lines, cfg, local_components)
        if lines:
            fused_lines = lines
            break
    return fused_lines


def detect_wires_experiment(
    image: np.ndarray,
    local_components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    cfg: ExperimentConfig,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    normalized = normalize_image(image, cfg.normalize_mode)
    masks = build_binary_masks(normalized, cfg)
    vote = cfg.threshold_vote if cfg.threshold_fusion_enabled else 1
    fused_mask, support_map = fuse_masks(masks, vote)

    if cfg.extraction_mode == "skeleton":
        skel_lines = extract_lines_from_skeleton(fused_mask, support_map, local_components, cfg)
        if cfg.hough_enabled:
            skel_candidates = [
                candidate_line_score(line, cfg, local_components, support_map, source="skeleton")
                for line in skel_lines
            ]
            all_candidates = skel_candidates + extract_lines_from_hough(
                fused_mask, support_map, local_components, cfg
            )
            topo_lines = topology_select_lines(all_candidates, local_components, cfg)
            filtered_candidates = [c for c in all_candidates if c.line in topo_lines]
            lines = dedup_by_score_cluster(filtered_candidates, cfg)
        else:
            lines = skel_lines
    else:
        lines = extract_lines_from_components(masks, local_components, cfg)

    lines = reconnect_lines(lines, local_components, cfg)
    lines = filter_component_connected_lines(lines, local_components, cfg)
    lines = add_secondary_recovery_lines(lines, normalized, local_components, cfg)
    lines = add_stroke_repairs(lines, normalized, support_map, local_components, cfg)
    lines = snap_line_endpoints(lines, local_components, cfg)
    return lines


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


def run_synthetic_experiment(
    cfg: ExperimentConfig,
    count: int = 40,
    seed: int = 123,
) -> dict[str, float | int]:
    sdg = SDG(
        SDGConfig(
            num_images=count,
            seed=seed,
            image_size=(512, 512),
            wires_per_image=(4, 10),
            components_count=(4, 8),
            components_size=(45, 110),
        )
    )

    tp_t = fp_t = fn_t = red_t = 0
    for image_idx in range(count):
        rng = np.random.default_rng(seed + image_idx)
        color, gt_lines = sdg.generate_one(rng)
        gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
        lines = detect_wires_experiment(gray, [], cfg)
        eval_result = ref.evaluate(lines, gt_lines)
        tp_t += eval_result[0]
        fp_t += eval_result[1]
        fn_t += eval_result[2]
        red_t += eval_result[3]

    precision = tp_t / max(tp_t + fp_t + red_t, 1)
    recall = tp_t / max(tp_t + fn_t, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    return {
        "global_f1": f1,
        "precision": precision,
        "recall": recall,
        "tp": tp_t,
        "fp": fp_t,
        "fn": fn_t,
        "red": red_t,
    }


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
    synthetic = run_synthetic_experiment(cfg)
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
        synthetic_f1=float(synthetic["global_f1"]),
        synthetic_precision=float(synthetic["precision"]),
        synthetic_recall=float(synthetic["recall"]),
        synthetic_tp=int(synthetic["tp"]),
        synthetic_fp=int(synthetic["fp"]),
        synthetic_fn=int(synthetic["fn"]),
        synthetic_red=int(synthetic["red"]),
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
                    "synthetic_f1": summary.synthetic_f1,
                    "synthetic_precision": summary.synthetic_precision,
                    "synthetic_recall": summary.synthetic_recall,
                    "synthetic_tp": summary.synthetic_tp,
                    "synthetic_fp": summary.synthetic_fp,
                    "synthetic_fn": summary.synthetic_fn,
                    "synthetic_red": summary.synthetic_red,
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


def wave3_configs() -> list[ExperimentConfig]:
    return [
        ExperimentConfig(name="baseline_control"),
        ExperimentConfig(
            name="skeleton_graph_v1",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            ccl_min_area=28,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=14.0,
            anchor_link_dist=8.0,
            graph_min_path_len=14.0,
        ),
        ExperimentConfig(
            name="best_candidate_v5",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
        ),
        ExperimentConfig(
            name="best_candidate_v7",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="best_candidate_v6",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=12.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=16.0,
            graph_port_dist=16.0,
        ),
        ExperimentConfig(
            name="best_candidate_v8",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=12.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=16.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="skeleton_graph_full",
            sauvola_k=0.2825,
            sauvola_window=67,
            close_kernel=3,
            fallback_ks=(0.25, 0.24),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=2,
            threshold_union_with_clahe=True,
            dedup_mode="score_cluster",
            reconnect_enabled=True,
            reconnect_gap=15.0,
            reconnect_angle=10.0,
            reconnect_boundary_dist=16.0,
            anchor_filter_enabled=True,
            anchor_endpoint_dist=14.0,
            anchor_link_dist=8.0,
            graph_min_path_len=12.0,
            graph_anchor_bonus=0.45,
            graph_support_bonus=0.7,
            graph_cluster_dist=10.0,
            graph_port_dist=20.0,
            secondary_recovery_enabled=True,
            secondary_recovery_overlap_dist=10.0,
            secondary_recovery_anchor_dist=18.0,
            secondary_recovery_link_dist=10.0,
        ),
        ExperimentConfig(
            name="skeleton_graph_recall",
            sauvola_k=0.2775,
            sauvola_window=61,
            close_kernel=3,
            fallback_ks=(0.25, 0.235),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            threshold_union_with_clahe=True,
            dedup_mode="score_cluster",
            reconnect_enabled=True,
            reconnect_gap=16.0,
            reconnect_angle=10.0,
            reconnect_boundary_dist=16.0,
            anchor_filter_enabled=True,
            anchor_endpoint_dist=14.0,
            anchor_link_dist=8.0,
            graph_min_path_len=10.0,
            graph_anchor_bonus=0.35,
            graph_support_bonus=0.55,
            graph_cluster_dist=11.0,
            graph_port_dist=20.0,
        ),
    ]


def wave4_configs() -> list[ExperimentConfig]:
    return [
        ExperimentConfig(name="baseline_control"),
        ExperimentConfig(
            name="otsu_component",
            threshold_method="otsu",
            threshold_blur=3,
            fallback_ks=(),
        ),
        ExperimentConfig(
            name="otsu_skeleton",
            threshold_method="otsu",
            threshold_blur=3,
            fallback_ks=(),
            extraction_mode="skeleton",
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="otsu_clahe_skeleton",
            threshold_method="otsu",
            threshold_blur=5,
            threshold_union_with_clahe=True,
            fallback_ks=(),
            extraction_mode="skeleton",
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.9,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.05,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="adaptive_mean_skeleton",
            threshold_method="adaptive_mean",
            threshold_block_size=61,
            threshold_c=10.0,
            fallback_ks=(),
            extraction_mode="skeleton",
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.5,
            graph_support_bonus=0.9,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.05,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="adaptive_gaussian_skeleton",
            threshold_method="adaptive_gaussian",
            threshold_block_size=61,
            threshold_c=8.0,
            fallback_ks=(),
            extraction_mode="skeleton",
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.5,
            graph_support_bonus=0.9,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.05,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="triangle_skeleton",
            threshold_method="triangle",
            threshold_blur=3,
            fallback_ks=(),
            extraction_mode="skeleton",
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.5,
            graph_support_bonus=0.9,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.05,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="sauvola_otsu_fusion",
            threshold_method="sauvola",
            extra_threshold_methods=("otsu",),
            sauvola_k=0.285,
            sauvola_window=67,
            threshold_blur=3,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="sauvola_adaptive_gaussian_fusion",
            threshold_method="sauvola",
            extra_threshold_methods=("adaptive_gaussian",),
            sauvola_k=0.285,
            sauvola_window=67,
            threshold_block_size=61,
            threshold_c=8.0,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=18.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.05,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="otsu_skeleton_reconnect",
            threshold_method="otsu",
            threshold_blur=3,
            fallback_ks=(),
            extraction_mode="skeleton",
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=17.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.9,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.05,
            topology_overlap_dist=10.0,
            reconnect_enabled=True,
            reconnect_gap=12.0,
            reconnect_angle=8.0,
            reconnect_boundary_dist=12.0,
        ),
    ]


def wave5_configs() -> list[ExperimentConfig]:
    return [
        ExperimentConfig(name="baseline_control"),
        ExperimentConfig(
            name="best_candidate_v7",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_recovery_a",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=61,
            secondary_threshold_c=8.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=8.0,
            secondary_recovery_anchor_dist=16.0,
            secondary_recovery_link_dist=8.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_recovery_b",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=10.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=8.0,
            secondary_recovery_anchor_dist=16.0,
            secondary_recovery_link_dist=8.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_recovery_c",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_extra_threshold_methods=("adaptive_mean",),
            secondary_threshold_block_size=61,
            secondary_threshold_c=8.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=8.0,
            secondary_recovery_anchor_dist=17.0,
            secondary_recovery_link_dist=8.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_recovery_d",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=0.95,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.1,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=10.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=14.0,
            secondary_recovery_link_dist=6.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_best",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=7.0,
            secondary_parallel_dist=10.0,
            secondary_endpoint_novelty_radius=10.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_fp_guard_a",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_fp_guard_b",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
            secondary_require_both_anchors=True,
        ),
        ExperimentConfig(
            name="hybrid_gaussian_fp_guard_c",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=12.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=5.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=5.0,
            secondary_parallel_dist=8.0,
            secondary_endpoint_novelty_radius=8.0,
        ),
    ]


def wave6_configs() -> list[ExperimentConfig]:
    base = ExperimentConfig(
        name="hybrid_topology_repair_a",
        threshold_method="sauvola",
        sauvola_k=0.285,
        sauvola_window=67,
        fallback_ks=(0.25,),
        extraction_mode="skeleton",
        threshold_fusion_enabled=True,
        threshold_vote=1,
        dedup_mode="score_cluster",
        anchor_filter_enabled=True,
        anchor_endpoint_dist=11.0,
        anchor_link_dist=6.0,
        graph_min_path_len=19.0,
        graph_anchor_bonus=0.55,
        graph_support_bonus=1.0,
        graph_cluster_dist=15.0,
        graph_port_dist=16.0,
        topology_filter_enabled=True,
        topology_endpoint_radius=12.0,
        topology_support_min=1.15,
        topology_overlap_dist=10.0,
        secondary_recovery_enabled=True,
        secondary_threshold_method="adaptive_gaussian",
        secondary_threshold_block_size=67,
        secondary_threshold_c=14.0,
        secondary_topology_filter_enabled=True,
        secondary_recovery_overlap_dist=6.0,
        secondary_recovery_anchor_dist=12.0,
        secondary_recovery_link_dist=6.0,
        secondary_parallel_reject_enabled=True,
        secondary_parallel_angle=6.0,
        secondary_parallel_dist=9.0,
        secondary_endpoint_novelty_radius=9.0,
        secondary_topology_driven=True,
        secondary_endpoint_seed_radius=8.0,
        secondary_endpoint_target_radius=10.0,
        secondary_max_repairs_per_seed=1,
    )
    return [
        ExperimentConfig(name="best_candidate_v7", threshold_method="sauvola", sauvola_k=0.285, sauvola_window=67, fallback_ks=(0.25,), extraction_mode="skeleton", threshold_fusion_enabled=True, threshold_vote=1, dedup_mode="score_cluster", anchor_filter_enabled=True, anchor_endpoint_dist=11.0, anchor_link_dist=6.0, graph_min_path_len=19.0, graph_anchor_bonus=0.55, graph_support_bonus=0.95, graph_cluster_dist=15.0, graph_port_dist=16.0, topology_filter_enabled=True, topology_endpoint_radius=12.0, topology_support_min=1.1, topology_overlap_dist=10.0),
        ExperimentConfig(
            name="hybrid_gaussian_fp_guard_b",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
            secondary_require_both_anchors=True,
        ),
        base,
        ExperimentConfig(
            **{
                **asdict(base),
                "name": "hybrid_topology_repair_b",
                "secondary_require_both_anchors": True,
                "secondary_endpoint_target_radius": 12.0,
            }
        ),
        ExperimentConfig(
            **{
                **asdict(base),
                "name": "hybrid_topology_repair_c",
                "secondary_endpoint_seed_radius": 10.0,
                "secondary_endpoint_target_radius": 12.0,
                "secondary_max_repairs_per_seed": 2,
            }
        ),
        ExperimentConfig(
            **{
                **asdict(base),
                "name": "hybrid_topology_repair_d",
                "secondary_require_both_anchors": True,
                "secondary_endpoint_seed_radius": 7.0,
                "secondary_endpoint_target_radius": 9.0,
                "secondary_parallel_angle": 5.0,
                "secondary_parallel_dist": 8.0,
            }
        ),
    ]


def wave7_configs() -> list[ExperimentConfig]:
    return [
        ExperimentConfig(
            name="hybrid_gaussian_fp_guard_b",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
            secondary_require_both_anchors=True,
        ),
        ExperimentConfig(
            name="hybrid_stroke_repair_a",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
            secondary_require_both_anchors=True,
            stroke_repair_enabled=True,
            stroke_repair_seed_radius=8.0,
            stroke_repair_target_radius=12.0,
            stroke_repair_max_gap=42.0,
            stroke_repair_support_min=1.18,
            stroke_repair_darkness_min=0.57,
            stroke_repair_max_per_seed=1,
        ),
        ExperimentConfig(
            name="hybrid_stroke_repair_b",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
            secondary_require_both_anchors=True,
            stroke_repair_enabled=True,
            stroke_repair_seed_radius=7.0,
            stroke_repair_target_radius=10.0,
            stroke_repair_max_gap=36.0,
            stroke_repair_support_min=1.22,
            stroke_repair_darkness_min=0.60,
            stroke_repair_max_per_seed=1,
        ),
        ExperimentConfig(
            name="hybrid_stroke_repair_c",
            threshold_method="sauvola",
            sauvola_k=0.285,
            sauvola_window=67,
            fallback_ks=(0.25,),
            extraction_mode="skeleton",
            threshold_fusion_enabled=True,
            threshold_vote=1,
            dedup_mode="score_cluster",
            anchor_filter_enabled=True,
            anchor_endpoint_dist=11.0,
            anchor_link_dist=6.0,
            graph_min_path_len=19.0,
            graph_anchor_bonus=0.55,
            graph_support_bonus=1.0,
            graph_cluster_dist=15.0,
            graph_port_dist=16.0,
            topology_filter_enabled=True,
            topology_endpoint_radius=12.0,
            topology_support_min=1.15,
            topology_overlap_dist=10.0,
            secondary_recovery_enabled=True,
            secondary_threshold_method="adaptive_gaussian",
            secondary_threshold_block_size=67,
            secondary_threshold_c=14.0,
            secondary_topology_filter_enabled=True,
            secondary_recovery_overlap_dist=6.0,
            secondary_recovery_anchor_dist=12.0,
            secondary_recovery_link_dist=6.0,
            secondary_parallel_reject_enabled=True,
            secondary_parallel_angle=6.0,
            secondary_parallel_dist=9.0,
            secondary_endpoint_novelty_radius=9.0,
            secondary_require_both_anchors=True,
            stroke_repair_enabled=True,
            stroke_repair_seed_radius=8.0,
            stroke_repair_target_radius=12.0,
            stroke_repair_max_gap=48.0,
            stroke_repair_support_min=1.14,
            stroke_repair_darkness_min=0.53,
            stroke_repair_max_per_seed=2,
        ),
    ]


def wave8_configs() -> list[ExperimentConfig]:
    base = ExperimentConfig(
        name="hybrid_gaussian_fp_guard_b",
        threshold_method="sauvola",
        sauvola_k=0.285,
        sauvola_window=67,
        fallback_ks=(0.25,),
        extraction_mode="skeleton",
        threshold_fusion_enabled=True,
        threshold_vote=1,
        dedup_mode="score_cluster",
        anchor_filter_enabled=True,
        anchor_endpoint_dist=11.0,
        anchor_link_dist=6.0,
        graph_min_path_len=19.0,
        graph_anchor_bonus=0.55,
        graph_support_bonus=1.0,
        graph_cluster_dist=15.0,
        graph_port_dist=16.0,
        topology_filter_enabled=True,
        topology_endpoint_radius=12.0,
        topology_support_min=1.15,
        topology_overlap_dist=10.0,
        secondary_recovery_enabled=True,
        secondary_threshold_method="adaptive_gaussian",
        secondary_threshold_block_size=67,
        secondary_threshold_c=14.0,
        secondary_topology_filter_enabled=True,
        secondary_recovery_overlap_dist=6.0,
        secondary_recovery_anchor_dist=12.0,
        secondary_recovery_link_dist=6.0,
        secondary_parallel_reject_enabled=True,
        secondary_parallel_angle=6.0,
        secondary_parallel_dist=9.0,
        secondary_endpoint_novelty_radius=9.0,
        secondary_require_both_anchors=True,
    )
    return [
        base,
        ExperimentConfig(**{**asdict(base), "name": "hybrid_port_gated_a", "class_port_gating_enabled": True}),
        ExperimentConfig(**{**asdict(base), "name": "hybrid_port_gated_complexity_a", "class_port_gating_enabled": True, "recovery_complexity_gate_enabled": True, "recovery_utility_min": 1.0}),
        ExperimentConfig(**{**asdict(base), "name": "hybrid_port_gated_complexity_b", "class_port_gating_enabled": True, "recovery_complexity_gate_enabled": True, "recovery_utility_min": 1.25}),
        ExperimentConfig(**{**asdict(base), "name": "hybrid_port_gated_complexity_c", "class_port_gating_enabled": True, "recovery_complexity_gate_enabled": True, "recovery_utility_min": 0.75, "secondary_recovery_link_dist": 7.0}),
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
            "synthetic_f1": summary.synthetic_f1,
            "synthetic_precision": summary.synthetic_precision,
            "synthetic_recall": summary.synthetic_recall,
            "beat_reference": summary.beat_reference,
            "config": asdict(summary.config),
        }
        for summary in ranking
    ]
    (output_dir / f"{preset_name}_ranking.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "| name | global_f1 | precision | recall | synthetic_f1 | synthetic_precision | synthetic_recall | tp | fp | fn | red | beat_reference |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in data:
        lines.append(
            f"| {row['name']} | {row['global_f1']:.4f} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['synthetic_f1']:.4f} | {row['synthetic_precision']:.4f} | {row['synthetic_recall']:.4f} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {row['red']} | {'yes' if row['beat_reference'] else 'no'} |"
        )
    (output_dir / f"{preset_name}_ranking.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark experiments against the frozen reference pipeline.")
    parser.add_argument("--preset", choices=["wave1", "wave2", "wave3", "wave4", "wave5", "wave6", "wave7", "wave8"], default="wave1")
    parser.add_argument("--output-dir", type=Path, default=Path("output/benchmark_experiments"))
    args = parser.parse_args()

    if args.preset == "wave1":
        configs = wave1_configs()
    elif args.preset == "wave2":
        configs = wave2_configs()
    elif args.preset == "wave3":
        configs = wave3_configs()
    elif args.preset == "wave4":
        configs = wave4_configs()
    elif args.preset == "wave5":
        configs = wave5_configs()
    elif args.preset == "wave6":
        configs = wave6_configs()
    elif args.preset == "wave7":
        configs = wave7_configs()
    else:
        configs = wave8_configs()
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
