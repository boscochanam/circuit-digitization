from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.backends.registry import PipelineBackend, register_backend


class SINA(PipelineBackend):
    def run(self, image: np.ndarray, params: dict[str, Any]) -> dict[str, Any]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        component_mask = params.get("component_mask")
        min_area = int(params.get("min_area", 30))

        if component_mask is not None:
            masked = gray.copy()
            masked[component_mask > 0] = 255
        else:
            masked = gray

        _, bw = cv2.threshold(masked, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv = cv2.bitwise_not(bw)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bw_inv, connectivity=8)
        nets = []
        for label_id in range(1, num_labels):
            area = stats[label_id, cv2.CC_STAT_AREA]
            if area >= min_area:
                nets.append(labels == label_id)

        return {
            "nets": nets,
            "net_count": len(nets),
        }


register_backend("sina", SINA)
