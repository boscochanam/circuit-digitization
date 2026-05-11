import random
import numpy as np
from typing import Tuple


def ccw(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float]) -> bool:
    return (p3[1] - p1[1]) * (p2[0] - p1[0]) > (p2[1] - p1[1]) * (p3[0] - p1[0])


def intersect(
    A: Tuple[float, float],
    B: Tuple[float, float],
    C: Tuple[float, float],
    D: Tuple[float, float],
) -> bool:
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def line_rect_intersection(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    rect: Tuple[int, int, int, int],
) -> bool:
    rx, ry, rw, rh = rect
    tl, tr = (rx, ry), (rx + rw, ry)
    bl, br = (rx, ry + rh), (rx + rw, ry + rh)
    return intersect(p1, p2, tl, br) or intersect(p1, p2, tr, bl)


def get_bezier_curve(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    control_scale: float = 0.15,
    num_points: int = 40,
    jitter: float = 0.4,
    **kwargs,
) -> np.ndarray:
    p0 = np.array(p0, dtype=float)
    p1 = np.array(p1, dtype=float)
    vec = p1 - p0
    dist = np.linalg.norm(vec)
    if dist == 0:
        return np.array([p0, p1], dtype=np.int32)
    perp = np.array([-vec[1], vec[0]]) / dist
    curve_direction = random.choice([1, -1])
    offset = dist * control_scale * random.uniform(0.3, 1.0) * curve_direction
    control_point = (p0 + p1) / 2 + perp * offset
    t = np.linspace(0, 1, num_points)[:, None]
    points = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * control_point + t ** 2 * p1
    if jitter > 0:
        jitter_vals = np.random.normal(0, jitter, points.shape)
        points += jitter_vals
    return points.astype(np.int32)


def get_connection_points(
    rect1: Tuple[int, int, int, int],
    rect2: Tuple[int, int, int, int],
    offset_range: int = 15,
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    p1 = (
        x1 + w1 // 2 + random.randint(-offset_range, offset_range),
        y1 + h1 // 2 + random.randint(-offset_range, offset_range),
    )
    p2 = (
        x2 + w2 // 2 + random.randint(-offset_range, offset_range),
        y2 + h2 // 2 + random.randint(-offset_range, offset_range),
    )
    return p1, p2


def calculate_bounding_box(
    points: np.ndarray,
    padding: int = 5,
) -> Tuple[float, float, float, float]:
    xs, ys = points[:, 0], points[:, 1]
    min_x, max_x = np.min(xs), np.max(xs)
    min_y, max_y = np.min(ys), np.max(ys)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    width = max_x - min_x + padding * 2
    height = max_y - min_y + padding * 2
    return center_x, center_y, width, height


def normalize_keypoints(
    keypoints: list[Tuple[int, int]],
    image_size: Tuple[int, int],
) -> list[Tuple[float, float, int]]:
    width, height = image_size
    normalized = []
    for x, y in keypoints:
        x_norm = x / width
        y_norm = y / height
        visibility = 2
        normalized.append((x_norm, y_norm, visibility))
    return normalized


def get_rect_edge_point(
    center: Tuple[float, float],
    target: Tuple[float, float],
    rect: Tuple[int, int, int, int],
) -> Tuple[int, int]:
    rx, ry, rw, rh = rect
    cx, cy = center
    tx, ty = target
    ix = max(rx, min(rx + rw, cx))
    iy = max(ry, min(ry + rh, cy))
    if ix == cx and iy == cy:
        dx = tx - cx
        dy = ty - cy
        if dx == 0 and dy == 0:
            return (int(cx), int(cy))
        dist_l = cx - rx
        dist_r = (rx + rw) - cx
        dist_t = cy - ry
        dist_b = (ry + rh) - cy
        scales = []
        if dx < 0: scales.append(dist_l / -dx)
        if dx > 0: scales.append(dist_r / dx)
        if dy < 0: scales.append(dist_t / -dy)
        if dy > 0: scales.append(dist_b / dy)
        scale = min(scales) if scales else 0
        ix = int(cx + dx * scale)
        iy = int(cy + dy * scale)
    return (int(ix), int(iy))
