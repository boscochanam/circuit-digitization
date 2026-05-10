from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


class ThresholdStage(PipelineStage):
    name = "threshold"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        mode = params.get("mode", "otsu")
        value = int(params.get("value", 127))
        block_size = int(params.get("block_size", 31))
        c = int(params.get("c", 2))

        if mode == "otsu":
            _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif mode == "adaptive":
            bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, block_size, c)
        elif mode == "canny":
            low = int(params.get("low", 50))
            high = int(params.get("high", 150))
            bw = cv2.Canny(gray, low, high)
        else:
            _, bw = cv2.threshold(gray, value, 255, cv2.THRESH_BINARY)

        return StageOutput(bw)
