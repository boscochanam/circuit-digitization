from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


class NormalizeStage(PipelineStage):
    """Normalization pre-processing: none, clahe, minmax, blackhat, tophat, median_sub."""
    name = "normalize"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        mode = params.get("mode", "none")

        if mode == "none":
            return StageOutput(gray)
        if mode == "minmax":
            return StageOutput(cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX))
        if mode == "clahe":
            clip = params.get("clip_limit", 2.0)
            tile = params.get("tile_size", 8)
            return StageOutput(cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile)).apply(gray))
        if mode == "blackhat":
            ks = params.get("kernel_size", 31)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
            return StageOutput(cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k))
        if mode == "tophat":
            ks = params.get("kernel_size", 15)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
            return StageOutput(cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k))
        if mode == "median_sub":
            ks = params.get("kernel_size", 31)
            return StageOutput(cv2.subtract(cv2.medianBlur(gray, ks), gray))
        if mode == "gaussian_norm":
            im = gray.astype(np.float32)
            m, s = im.mean(), im.std()
            return StageOutput(np.clip(((im - m) / max(s, 1) * 64 + 128), 0, 255).astype(np.uint8))
        return StageOutput(gray)
