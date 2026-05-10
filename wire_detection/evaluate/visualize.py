import cv2
import numpy as np


def visualize_detections(
    image: np.ndarray,
    detections: list[tuple[tuple[int, int], tuple[int, int]]],
    ground_truth: list[tuple[tuple[int, int], tuple[int, int]]] | None = None,
) -> np.ndarray:
    vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if len(image.shape) == 2 else image.copy()

    for p1, p2 in detections:
        cv2.line(vis, p1, p2, (0, 255, 0), 2)

    if ground_truth:
        for p1, p2 in ground_truth:
            cv2.line(vis, p1, p2, (0, 0, 255), 1)

    return vis
