import math
import random
from typing import Any
import numpy as np


def get_bezier_curve(
    p1: tuple[float, float],
    p2: tuple[float, float],
    num_points: int = 50,
    rng: random.Random | None = None,
) -> np.ndarray:
    if rng is None:
        rng = random
    x1, y1 = p1
    x2, y2 = p2
    dist = math.hypot(x2 - x1, y2 - y1)

    num_cp = rng.choice([1, 2])
    cps = [(x1, y1)]

    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2

    if num_cp == 1:
        offset = dist * rng.uniform(0.1, 0.4) * rng.choice([-1, 1])
        perp_x = -(y2 - y1) / max(dist, 1)
        perp_y = (x2 - x1) / max(dist, 1)
        cps.append((mid_x + perp_x * offset, mid_y + perp_y * offset))
    else:
        offset1 = dist * rng.uniform(0.1, 0.3) * rng.choice([-1, 1])
        offset2 = dist * rng.uniform(0.1, 0.3) * rng.choice([-1, 1])
        perp_x = -(y2 - y1) / max(dist, 1)
        perp_y = (x2 - x1) / max(dist, 1)
        t1, t2 = 0.3, 0.7
        cps.append((
            (1 - t1) * x1 + t1 * x2 + perp_x * offset1,
            (1 - t1) * y1 + t1 * y2 + perp_y * offset1,
        ))
        cps.append((
            (1 - t2) * x1 + t2 * x2 + perp_x * offset2,
            (1 - t2) * y1 + t2 * y2 + perp_y * offset2,
        ))

    cps.append((x2, y2))

    n = len(cps) - 1
    curve = np.zeros((num_points, 2), dtype=np.int32)
    for i, t in enumerate(np.linspace(0, 1, num_points)):
        pts = list(cps)
        for r in range(n):
            new_pts = []
            for j in range(n - r):
                new_x = (1 - t) * pts[j][0] + t * pts[j + 1][0]
                new_y = (1 - t) * pts[j][1] + t * pts[j + 1][1]
                new_pts.append((new_x, new_y))
            pts = new_pts
        curve[i] = [int(pts[0][0]), int(pts[0][1])]

    return curve


def get_rect_edge_point(
    p_inner: tuple[float, float],
    p_outer: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> tuple[int, int]:
    rx, ry, rw, rh = rect
    edges = [
        ((rx, ry), (rx + rw, ry)),
        ((rx + rw, ry), (rx + rw, ry + rh)),
        ((rx + rw, ry + rh), (rx, ry + rh)),
        ((rx, ry + rh), (rx, ry)),
    ]

    def ccw(p1, p2, p3):
        return (p3[1] - p1[1]) * (p2[0] - p1[0]) > (p2[1] - p1[1]) * (p3[0] - p1[0])

    def intersect(A, B, C, D):
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

    A = np.array(p_inner)
    B = np.array(p_outer)
    for E1, E2 in edges:
        E1a, E2a = np.array(E1), np.array(E2)
        if intersect(A, B, E1a, E2a):
            da = B - A
            db = E2a - E1a
            dp = A - E1a
            dap = np.array([-da[1], da[0]])
            denom = np.dot(dap, db)
            if denom == 0:
                continue
            t = np.dot(dap, dp) / denom
            return tuple((E1a + t * db).astype(int))

    cx = max(rx, min(rx + rw, p_outer[0]))
    cy = max(ry, min(ry + rh, p_outer[1]))
    return (int(cx), int(cy))


def draw_tool_stroke(
    canvas: np.ndarray,
    points: np.ndarray,
    tool_type: str = "gel",
    rng: random.Random | None = None,
) -> None:
    import cv2
    if rng is None:
        rng = random

    thickness = 1
    if tool_type == "pencil":
        c = rng.randint(80, 140)
        color = (c, c, c)
        cv2.polylines(canvas, [points], False, color, thickness, cv2.LINE_AA)
    elif tool_type == "ballpoint":
        if rng.random() < 0.3:
            color = (rng.randint(150, 200), rng.randint(50, 100), rng.randint(50, 100))
        else:
            c = rng.randint(60, 100)
            color = (c, c, c)
        cv2.polylines(canvas, [points], False, color, thickness, cv2.LINE_AA)
    elif tool_type == "gel":
        c = rng.randint(30, 60)
        color = (c, c, c)
        cv2.polylines(canvas, [points], False, color, thickness, cv2.LINE_AA)
