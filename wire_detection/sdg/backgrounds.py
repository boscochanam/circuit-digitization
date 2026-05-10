from typing import Any
import numpy as np
import cv2


def generate_plain_background(
    size: tuple[int, int],
    color: int = 255,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    return np.full((size[1], size[0]), color, dtype=np.uint8)


def generate_grid_background(
    size: tuple[int, int],
    grid_size: int = 50,
    line_thickness: int = 1,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    h, w = size[1], size[0]
    bg = np.full((h, w), 255, dtype=np.uint8)
    for x in range(0, w, grid_size):
        cv2.line(bg, (x, 0), (x, h), 200, line_thickness)
    for y in range(0, h, grid_size):
        cv2.line(bg, (0, y), (w, y), 200, line_thickness)
    return bg


def generate_noise_background(
    size: tuple[int, int],
    noise_type: str = "gaussian",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng()
    h, w = size[1], size[0]

    if noise_type == "gaussian":
        noise = rng.normal(128, 30, (h, w)).astype(np.uint8)
    elif noise_type == "salt_pepper":
        bg = np.full((h, w), 255, dtype=np.uint8)
        mask = rng.random((h, w))
        bg[mask < 0.02] = 0
        bg[mask > 0.98] = 255
        noise = bg
    else:
        noise = rng.integers(200, 256, (h, w), dtype=np.uint8)

    return noise
