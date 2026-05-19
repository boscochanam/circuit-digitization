from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


class CloseStage(PipelineStage):
    """Morphological close (dilate then erode) to bridge gaps in binary lines."""
    name = "close"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        kernel_size = int(params.get("kernel_size", 3))
        iterations = int(params.get("iterations", 1))
        shape_name = params.get("shape", "ellipse")

        if kernel_size < 1 or iterations < 1:
            return StageOutput(image)

        shape_map = {
            "rect": cv2.MORPH_RECT,
            "cross": cv2.MORPH_CROSS,
            "ellipse": cv2.MORPH_ELLIPSE,
        }
        morph_shape = shape_map.get(shape_name, cv2.MORPH_ELLIPSE)
        kernel = cv2.getStructuringElement(morph_shape, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel, iterations=iterations)
        return StageOutput(closed)


class MergeStage(PipelineStage):
    """Merge collinear lines that are within a distance gap."""
    name = "merge"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        lines: list = params.get("_lines", [])
        gap_thresh = float(params.get("gap_thresh", 20))
        angle_thresh = float(params.get("angle_thresh", 15))

        if not lines:
            return StageOutput(image, {"lines": lines})

        merged = _merge_collinear(lines, angle_thresh, gap_thresh)
        return StageOutput(image, {"lines": merged})


def _merge_collinear(lines, angle_thresh=15, gap_thresh=40):
    import math
    if not lines:
        return []
    r = list(lines)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(r):
            j = i + 1
            while j < len(r):
                p1, p2 = r[i]
                q1, q2 = r[j]
                dx1, dy1 = p2[0] - p1[0], p2[1] - p1[1]
                dx2, dy2 = q2[0] - q1[0], q2[1] - q1[1]
                l1, l2 = math.hypot(dx1, dy1), math.hypot(dx2, dy2)
                if l1 < 1 or l2 < 1:
                    j += 1
                    continue
                a = math.degrees(math.acos(max(-1, min(1, (dx1 * dx2 + dy1 * dy2) / (l1 * l2)))))
                if a > angle_thresh:
                    j += 1
                    continue
                mg = min(
                    math.hypot(p1[0] - q1[0], p1[1] - q1[1]),
                    math.hypot(p1[0] - q2[0], p1[1] - q2[1]),
                    math.hypot(p2[0] - q1[0], p2[1] - q1[1]),
                    math.hypot(p2[0] - q2[0], p2[1] - q2[1]),
                )
                if mg <= gap_thresh:
                    ap = [p1, p2, q1, q2]
                    md = -1
                    bp = (p1, q1)
                    for a2 in range(4):
                        for b2 in range(a2 + 1, 4):
                            d2 = math.hypot(ap[a2][0] - ap[b2][0], ap[a2][1] - ap[b2][1])
                            if d2 > md:
                                md, bp = d2, (ap[a2], ap[b2])
                    r[i] = bp
                    r.pop(j)
                    changed = True
                else:
                    j += 1
            i += 1
    return r
