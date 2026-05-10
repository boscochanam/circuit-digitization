from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import numpy as np
from pydantic import BaseModel
from typing import Literal


class SDGConfig(BaseModel):
    num_images: int = 1000
    wires_per_image: tuple[int, int] = (3, 15)
    wire_width: tuple[int, int] = (1, 4)
    wire_types: list[Literal["bezier", "line", "arc"]] = ["bezier"]
    background_types: list[str] = ["plain", "grid", "noise"]
    image_size: tuple[int, int] = (1024, 1024)
    output_dir: Path = Path("output/sdg")
    label_format: Literal["yolov8_pose", "coco", "lines"] = "yolov8_pose"
    seed: int | None = None


@dataclass
class DatasetMetadata:
    image_paths: list[Path] = field(default_factory=list)
    label_paths: list[Path] = field(default_factory=list)
    num_images: int = 0
    config: dict[str, Any] = field(default_factory=dict)


class SDG:
    def __init__(self, cfg: SDGConfig):
        self.cfg = cfg

    def generate(self) -> DatasetMetadata:
        import random as stdlib_random
        rng_seed = self.cfg.seed if self.cfg.seed is not None else stdlib_random.randint(0, 2**31 - 1)
        np_rng = np.random.default_rng(rng_seed)
        py_rng = stdlib_random.Random(rng_seed)

        output_dir = Path(self.cfg.output_dir)
        images_dir = output_dir / "images"
        labels_dir = output_dir / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        image_paths = []
        label_paths = []

        for i in range(self.cfg.num_images):
            img, lines = self.generate_one(np_rng)
            img_path = images_dir / f"syn_{i:06d}.jpg"
            label_path = labels_dir / f"syn_{i:06d}.txt"

            import cv2
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
                if isinstance(v, Path): return str(v)
                if isinstance(v, dict): return {kk: convert(vv) for kk, vv in v.items()}
                if isinstance(v, (list, tuple)): return [convert(i) for i in v]
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
        import random as stdlib_random
        from wire_detection.sdg.compositor import compose_image

        py_rng = stdlib_random.Random(int(rng.integers(0, 2**31)))
        W, H = self.cfg.image_size

        num_wires = py_rng.randint(*self.cfg.wires_per_image)
        wires = []
        for _ in range(num_wires):
            x1 = py_rng.randint(50, W - 50)
            y1 = py_rng.randint(50, H - 50)
            x2 = py_rng.randint(50, W - 50)
            y2 = py_rng.randint(50, H - 50)
            wires.append(((x1, y1), (x2, y2)))

        bg_type = py_rng.choice(self.cfg.background_types)
        image = compose_image(
            self.cfg.image_size,
            wires,
            background_type=bg_type,
            tool_types=["gel", "ballpoint", "pencil"],
            rng=rng,
        )

        return image, wires
