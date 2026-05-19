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
        elif mode == "adapt_mean":
            bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, block_size, c)
        elif mode == "canny":
            low = int(params.get("low", 50))
            high = int(params.get("high", 150))
            bw = cv2.Canny(gray, low, high)
        elif mode == "sauvola":
            k = float(params.get("k", 0.3))
            r = float(params.get("r", 128))
            window = int(params.get("window", 51))
            fallback_k = float(params.get("fallback_k", 0.25))
            min_trace = float(params.get("min_trace", 0.5))
            
            for try_k in [k, fallback_k]:
                mean = cv2.boxFilter(gray.astype(np.float32), -1, (window, window), normalize=True)
                sqr = cv2.boxFilter((gray.astype(np.float32)) ** 2, -1, (window, window), normalize=True)
                std = np.sqrt(np.maximum(sqr - mean ** 2, 0))
                t = mean * (1 + try_k * (std / r - 1))
                bw_raw = (gray > t).astype(np.uint8) * 255
                bw_inv = cv2.bitwise_not(bw_raw)
                if try_k == k:
                    trace_pct = (bw_inv > 0).mean() * 100
                    if trace_pct >= min_trace:
                        bw = bw_inv
                        break
                else:
                    bw = bw_inv
                    break
            else:
                bw = bw_inv  # never happens
        else:
            _, bw = cv2.threshold(gray, value, 255, cv2.THRESH_BINARY)

        return StageOutput(bw)
