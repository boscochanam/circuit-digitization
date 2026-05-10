from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


class DilateStage(PipelineStage):
    name = "dilate"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        kernel_size = int(params.get("kernel_size", 5))
        iterations = int(params.get("iterations", 1))
        shape_name = params.get("shape", "rect")

        shape_map = {
            "rect": cv2.MORPH_RECT,
            "cross": cv2.MORPH_CROSS,
            "ellipse": cv2.MORPH_ELLIPSE,
        }
        morph_shape = shape_map.get(shape_name, cv2.MORPH_RECT)
        kernel = cv2.getStructuringElement(morph_shape, (kernel_size, kernel_size))

        if iterations > 0:
            dilated = cv2.dilate(image, kernel, iterations=iterations)
        else:
            dilated = image

        return StageOutput(dilated)
