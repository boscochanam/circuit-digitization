import math


def point_to_segment_dist(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-8)
    t = max(0, min(1, t))
    projx = ax + t * abx
    projy = ay + t * aby
    return math.hypot(px - projx, py - projy)


def segment_dist(
    det: tuple[tuple[float, float], tuple[float, float]],
    gt: tuple[tuple[float, float], tuple[float, float]],
) -> float:
    p1, p2 = det
    g1, g2 = gt
    return (point_to_segment_dist(p1, g1, g2) + point_to_segment_dist(p2, g1, g2)) / 2
