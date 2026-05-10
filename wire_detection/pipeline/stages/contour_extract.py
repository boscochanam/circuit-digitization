from typing import Any
import numpy as np
import cv2
import math
from wire_detection.pipeline.types import PipelineStage, StageOutput, Line
from wire_detection.pipeline.stages.ccl import ccl_components


def find_endpoints(mask: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]] | tuple[None, None]:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None

    cnt = max(contours, key=cv2.contourArea)
    left = tuple(cnt[cnt[:, :, 0].argmin()][0])
    right = tuple(cnt[cnt[:, :, 0].argmax()][0])
    top = tuple(cnt[cnt[:, :, 1].argmin()][0])
    bottom = tuple(cnt[cnt[:, :, 1].argmax()][0])

    candidates = [left, right, top, bottom]
    best_dist = -1
    best_pair = (None, None)
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            dx = candidates[i][0] - candidates[j][0]
            dy = candidates[i][1] - candidates[j][1]
            dist = dx * dx + dy * dy
            if dist > best_dist:
                best_dist = dist
                best_pair = (candidates[i], candidates[j])
    return best_pair


def extract_lines_from_blobs(binary: np.ndarray, min_area: int = 30) -> list[Line]:
    comps = ccl_components(binary, min_area=min_area)
    lines = []
    for comp in comps:
        p1, p2 = find_endpoints(comp)
        if p1 is not None and p2 is not None:
            lines.append(((int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))))
    return lines


class ContourExtractStage(PipelineStage):
    name = "contour_extract"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        min_area = int(params.get("min_area", 30))
        lines = extract_lines_from_blobs(image, min_area=min_area)
        return StageOutput(image, {"lines": lines})
