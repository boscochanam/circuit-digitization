from typing import Any
import numpy as np
from wire_detection.pipeline.types import PipelineStage, StageOutput


class CropStage(PipelineStage):
    name = "crop"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        padding = params.get("padding", 10)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        h, w = gray.shape
        x1, y1, x2, y2 = padding, padding, w - padding, h - padding
        cropped = gray[y1:y2, x1:x2]
        return StageOutput(cropped)


import cv2
