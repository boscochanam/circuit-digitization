from typing import Any
import numpy as np
from wire_detection.sdg.backgrounds import (
    generate_plain_background,
    generate_grid_background,
    generate_noise_background,
)
from wire_detection.sdg.primitives import get_bezier_curve, draw_tool_stroke


BACKGROUND_GENERATORS = {
    "plain": generate_plain_background,
    "grid": generate_grid_background,
    "noise": generate_noise_background,
}


def compose_image(
    size: tuple[int, int],
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    background_type: str = "plain",
    tool_types: list[str] | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng()

    gen = BACKGROUND_GENERATORS.get(background_type, generate_plain_background)
    image = gen(size, rng=rng)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    import random as stdlib_random
    py_rng = stdlib_random.Random(int(rng.integers(0, 2**31)))

    for p1, p2 in wires:
        tool = py_rng.choice(tool_types or ["gel"])
        curve = get_bezier_curve(p1, p2, rng=py_rng)
        draw_tool_stroke(image_rgb, curve, tool_type=tool, rng=py_rng)

    return image_rgb


import cv2
import random
