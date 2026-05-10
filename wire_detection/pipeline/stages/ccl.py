from typing import Any
import numpy as np
import cv2
from wire_detection.pipeline.types import PipelineStage, StageOutput


def ccl_components(binary: np.ndarray, min_area: int = 30, connectivity: int = 8) -> list[np.ndarray]:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=connectivity)
    comps = []
    for label_id in range(1, num_labels):
        area = stats[label_id, cv2.CC_STAT_AREA]
        if area >= min_area:
            comps.append(labels == label_id)
    return comps


class CCLStage(PipelineStage):
    name = "ccl"

    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        min_area = int(params.get("min_area", 30))
        connectivity = int(params.get("connectivity", 8))
        backend = params.get("backend", "opencv")

        if backend == "scipy":
            from scipy import ndimage as ndi
            labeled, num_features = ndi.label(image)
            comps = []
            for label_id in range(1, num_features + 1):
                mask = labeled == label_id
                area = mask.sum()
                if area >= min_area:
                    comps.append(mask)
        else:
            comps = ccl_components(image, min_area, connectivity)

        return StageOutput(image, {"components": comps, "count": len(comps)})
