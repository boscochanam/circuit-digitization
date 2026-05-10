from pathlib import Path
from typing import Any
import numpy as np


def export_yolov8_pose(
    wire_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    image_size: tuple[int, int],
    output_path: str,
) -> None:
    IW, IH = image_size
    annotations = []

    for p1, p2 in wire_lines:
        if p1[0] < p2[0]:
            kpts = [p1, p2]
        else:
            kpts = [p2, p1]

        xs = [p1[0], p2[0]]
        ys = [p1[1], p2[1]]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        bw = max(xs) - min(xs) + 10
        bh = max(ys) - min(ys) + 10

        ann = [
            0,
            cx / IW, cy / IH, bw / IW, bh / IH,
            kpts[0][0] / IW, kpts[0][1] / IH, 2,
            kpts[1][0] / IW, kpts[1][1] / IH, 2,
        ]
        annotations.append(" ".join(map(str, ann)))

    with open(output_path, "w") as f:
        f.write("\n".join(annotations))


def export_lines(
    wire_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    output_path: str,
) -> None:
    annotations = []
    for p1, p2 in wire_lines:
        annotations.append(f"{p1[0]} {p1[1]} {p2[0]} {p2[1]}")
    with open(output_path, "w") as f:
        f.write("\n".join(annotations))
