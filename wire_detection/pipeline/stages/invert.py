from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


class InvertStage(PipelineStage):
    name = "invert"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        return StageOutput(cv2.bitwise_not(image))
