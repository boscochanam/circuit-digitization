from typing import Any
import math
import numpy as np
from wire_detection.pipeline.types import PipelineStage, StageOutput, Line


def filter_short_lines(lines: list[Line], min_length: int = 0, max_length: int = 0) -> list[Line]:
    kept = []
    for p1, p2 in lines:
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        length = math.hypot(dx, dy)
        if length >= min_length:
            if max_length <= 0 or length <= max_length:
                kept.append((p1, p2))
    return kept


class LengthFilterStage(PipelineStage):
    name = "length_filter"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        lines: list[Line] = params.get("_lines", [])
        min_length = int(params.get("min_length", 0))
        max_length = int(params.get("max_length", 0))
        filtered = filter_short_lines(lines, min_length=min_length, max_length=max_length)
        return StageOutput(image, {"lines": filtered})
