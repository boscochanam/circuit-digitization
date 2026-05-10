from typing import Any
import math
import numpy as np
from wire_detection.pipeline.types import PipelineStage, StageOutput, Line


def point_line_dist(pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    px, py = pt
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-8)
    t = max(0, min(1, t))
    projx = ax + t * abx
    projy = ay + t * aby
    return math.hypot(px - projx, py - projy)


def global_dedup(lines: list[Line], angle: float = 10, dist: float = 12) -> list[Line]:
    if not lines or angle <= 0:
        return lines

    kept = list(lines)
    a_thresh_rad = math.radians(angle)
    changed = True

    while changed:
        changed = False
        i = 0
        while i < len(kept):
            j = i + 1
            while j < len(kept):
                p1, p2 = kept[i]
                q1, q2 = kept[j]

                dx1 = p2[0] - p1[0]
                dy1 = p2[1] - p1[1]
                dx2 = q2[0] - q1[0]
                dy2 = q2[1] - q1[1]
                len1 = math.hypot(dx1, dy1)
                len2 = math.hypot(dx2, dy2)
                if len1 < 1 or len2 < 1:
                    j += 1
                    continue

                dot = dx1 * dx2 + dy1 * dy2
                angle_between = math.acos(max(-1, min(1, dot / (len1 * len2))))
                if angle_between > a_thresh_rad:
                    j += 1
                    continue

                longer = kept[i] if len1 >= len2 else kept[j]
                shorter = kept[j] if len1 >= len2 else kept[i]

                d1 = point_line_dist(shorter[0], longer[0], longer[1])
                d2 = point_line_dist(shorter[1], longer[0], longer[1])

                if d1 <= dist and d2 <= dist:
                    kept.pop(j)
                    changed = True
                else:
                    j += 1
            i += 1
    return kept


class DedupStage(PipelineStage):
    name = "dedup"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        lines: list[Line] = params.get("_lines", [])
        angle = float(params.get("angle_thresh", 10))
        dist = float(params.get("dist_thresh", 12))
        deduped = global_dedup(lines, angle=angle, dist=dist)
        return StageOutput(image, {"lines": deduped})
