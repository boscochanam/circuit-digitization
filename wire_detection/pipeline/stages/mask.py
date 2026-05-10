from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


class MaskStage(PipelineStage):
    name = "mask"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        fill_value = params.get("fill_value", 255)
        return StageOutput(image)

    def set_mask(self, image: np.ndarray, polygons: list[np.ndarray], fill_value: int = 255) -> np.ndarray:
        masked = image.copy()
        for poly in polygons:
            cv2.fillPoly(masked, [poly], fill_value)
        return masked
