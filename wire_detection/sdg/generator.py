import json
import math
import random as stdlib_random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import cv2
import numpy as np
from pydantic import BaseModel

from wire_detection.sdg.backgrounds import BackgroundLoader
from wire_detection.sdg.primitives import (
    intersect, line_rect_intersection, get_bezier_curve,
    calculate_bounding_box, normalize_keypoints, get_rect_edge_point,
)
from wire_detection.sdg.textures import add_paper_imperfections, draw_tool_stroke


class SDGConfig(BaseModel):
    num_images: int = 1000
    wires_per_image: tuple[int, int] = (3, 15)
    image_size: tuple[int, int] = (1024, 1024)
    output_dir: Path = Path("output/sdg")
    label_format: Literal["yolov8_pose", "coco", "lines"] = "yolov8_pose"
    seed: int | None = None

    components_count: tuple[int, int] = (4, 8)
    components_size: tuple[int, int] = (50, 130)
    safe_buffer: int = 15

    tool_weights: dict[str, float] = {"gel": 0.4, "ballpoint": 0.4, "pencil": 0.2}

    control_scale: float = 0.15
    num_points: int = 40
    jitter: float = 0.4

    bg_source_dir: Path | None = None
    bg_crop_mode: str = "random"
    bg_fallback_to_synthetic: bool = True


@dataclass
class DatasetMetadata:
    image_paths: list[Path] = field(default_factory=list)
    label_paths: list[Path] = field(default_factory=list)
    num_images: int = 0
    config: dict[str, Any] = field(default_factory=dict)


class SDG:
    def __init__(self, cfg: SDGConfig):
        self.cfg = cfg
        if cfg.seed is not None:
            stdlib_random.seed(cfg.seed)
            np.random.seed(cfg.seed)
        self.background_loader = BackgroundLoader(
            source_dir=cfg.bg_source_dir,
            target_size=cfg.image_size,
            crop_mode=cfg.bg_crop_mode,
            fallback_to_synthetic=cfg.bg_fallback_to_synthetic,
        )

    def generate(self) -> DatasetMetadata:
        output_dir = Path(self.cfg.output_dir)
        images_dir = output_dir / "images"
        labels_dir = output_dir / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        image_paths = []
        label_paths = []
        for i in range(self.cfg.num_images):
            rng = np.random.default_rng(
                self.cfg.seed + i if self.cfg.seed is not None
                else stdlib_random.randint(0, 2 ** 31 - 1)
            )
            img, lines = self.generate_one(rng)
            img_path = images_dir / f"syn_{i:06d}.jpg"
            label_path = labels_dir / f"syn_{i:06d}.txt"
            cv2.imwrite(str(img_path), img)
            image_paths.append(img_path)
            if self.cfg.label_format == "yolov8_pose":
                from wire_detection.sdg.formats import export_yolov8_pose
                export_yolov8_pose(lines, self.cfg.image_size, str(label_path))
            elif self.cfg.label_format == "lines":
                from wire_detection.sdg.formats import export_lines
                export_lines(lines, str(label_path))
            label_paths.append(label_path)
        metadata = DatasetMetadata(
            image_paths=image_paths,
            label_paths=label_paths,
            num_images=self.cfg.num_images,
            config=self.cfg.model_dump(),
        )

        def serialize_cfg(cfg_dict):
            def convert(v):
                if isinstance(v, Path):
                    return str(v)
                if isinstance(v, dict):
                    return {kk: convert(vv) for kk, vv in v.items()}
                if isinstance(v, (list, tuple)):
                    return [convert(i) for i in v]
                return v
            return convert(cfg_dict)

        with open(output_dir / "metadata.json", "w") as f:
            f.write(json.dumps({
                "num_images": metadata.num_images,
                "config": serialize_cfg(metadata.config),
                "images": [str(p) for p in metadata.image_paths],
                "labels": [str(p) for p in metadata.label_paths],
            }, indent=2))
        return metadata

    def generate_one(
        self, rng: np.random.Generator
    ) -> tuple[np.ndarray, list[tuple[tuple[int, int], tuple[int, int]]]]:
        py_rng = stdlib_random.Random(int(rng.integers(0, 2 ** 31)))
        np_rng = rng

        self._py_rng = py_rng
        self._np_rng = np_rng

        canvas = self.background_loader.get_background()
        canvas = add_paper_imperfections(canvas)

        components = self._generate_components()
        for x, y, w, h in components:
            c = py_rng.randint(200, 240)
            cv2.rectangle(canvas, (x, y), (x + w, y + h), (c, c, c), -1)

        edges = self._generate_connections(components)
        lines = []
        for edge in edges:
            result = self._draw_line(canvas, edge, components)
            if result:
                lines.append(result)

        return canvas, lines

    def _generate_components(self) -> list[tuple[int, int, int, int]]:
        components = []
        target_count = self._py_rng.randint(*self.cfg.components_count)
        attempts = 0
        max_attempts = 200
        img_w, img_h = self.cfg.image_size
        min_sz, max_sz = self.cfg.components_size
        max_sz = min(max_sz, img_w - 20, img_h - 20)
        while len(components) < target_count and attempts < max_attempts:
            w = self._py_rng.randint(min_sz, max_sz)
            h = self._py_rng.randint(min_sz, max_sz)
            x = self._py_rng.randint(10, img_w - w - 10)
            y = self._py_rng.randint(10, img_h - h - 10)
            new_rect = (x, y, w, h)
            overlap = False
            for ex, ey, ew, eh in components:
                buffer = self.cfg.safe_buffer
                if (x < ex + ew + buffer and x + w + buffer > ex and
                        y < ey + eh + buffer and y + h + buffer > ey):
                    overlap = True
                    break
            if not overlap:
                components.append(new_rect)
            attempts += 1
        return components

    def _generate_connections(
        self, components: list[tuple[int, int, int, int]]
    ) -> list[dict[str, Any]]:
        centers = [
            (c[0] + c[2] // 2, c[1] + c[3] // 2)
            for c in components
        ]
        potential_edges = []
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                dist = math.hypot(
                    centers[i][0] - centers[j][0],
                    centers[i][1] - centers[j][1]
                )
                potential_edges.append({"u": i, "v": j, "dist": dist})
        potential_edges.sort(key=lambda x: x["dist"])
        accepted_edges = []
        for edge in potential_edges:
            u, v = edge["u"], edge["v"]
            rect_u, rect_v = components[u], components[v]
            cp1 = centers[u]
            cp2 = centers[v]
            def find_edge_intersection(p1, p2, rect):
                rx, ry, rw, rh = rect
                cx, cy = p1
                tx, ty = p2
                ix = max(rx, min(rx + rw, cx))
                iy = max(ry, min(ry + rh, cy))
                if ix == cx and iy == cy:
                    dx = tx - cx
                    dy = ty - cy
                    if dx == 0 and dy == 0:
                        return (int(cx), int(cy))
                    dist_l = cx - rx
                    dist_r = (rx + rw) - cx
                    dist_t = cy - ry
                    dist_b = (ry + rh) - cy
                    scales = []
                    if dx < 0:
                        scales.append(dist_l / -dx)
                    if dx > 0:
                        scales.append(dist_r / dx)
                    if dy < 0:
                        scales.append(dist_t / -dy)
                    if dy > 0:
                        scales.append(dist_b / dy)
                    scale = min(scales) if scales else 0
                    ix = int(cx + dx * scale)
                    iy = int(cy + dy * scale)
                return (int(ix), int(iy))
            p1 = find_edge_intersection(cp1, cp2, rect_u)
            p2 = find_edge_intersection(cp2, cp1, rect_v)
            offset = 10
            p1 = (p1[0] + self._py_rng.randint(-offset, offset),
                  p1[1] + self._py_rng.randint(-offset, offset))
            p2 = (p2[0] + self._py_rng.randint(-offset, offset),
                  p2[1] + self._py_rng.randint(-offset, offset))
            clean = True
            for existing in accepted_edges:
                if intersect(p1, p2, existing["p1"], existing["p2"]):
                    clean = False
                    break
            if clean:
                for k, rect in enumerate(components):
                    if k == u or k == v:
                        continue
                    if line_rect_intersection(p1, p2, rect):
                        clean = False
                        break
            if clean:
                accepted_edges.append({
                    "u": u, "v": v,
                    "p1": p1, "p2": p2,
                })
        return accepted_edges

    def _draw_line(
        self,
        canvas: np.ndarray,
        edge: dict[str, Any],
        components: list[tuple[int, int, int, int]],
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        p1, p2 = edge["p1"], edge["p2"]
        vec = np.array(p2) - np.array(p1)
        length = np.linalg.norm(vec)
        if length == 0:
            return None
        dir_vec = vec / length
        draw_p1 = np.array(p1) - dir_vec * self._py_rng.uniform(-5, 10)
        draw_p2 = np.array(p2) + dir_vec * self._py_rng.uniform(-5, 10)
        path = get_bezier_curve(
            draw_p1, draw_p2,
            control_scale=self.cfg.control_scale,
            num_points=self.cfg.num_points,
            jitter=self.cfg.jitter,
        )
        tools = list(self.cfg.tool_weights.keys())
        weights = list(self.cfg.tool_weights.values())
        tool = self._py_rng.choices(tools, weights=weights)[0]
        draw_tool_stroke(canvas, path, tool)
        return (tuple(int(v) for v in p1), tuple(int(v) for v in p2))
