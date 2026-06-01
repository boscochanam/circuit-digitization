from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
import yaml


@dataclass
class DatasetConfig:
    key: str
    path: Path
    image_glob: str
    label_format: str | None = None
    label_glob: str | None = None
    component_labels: bool = False
    crop_to_components: bool = False
    description: str = ""


@dataclass
class WireLine:
    p1: tuple[int, int]
    p2: tuple[int, int]


HDC_SPLITS = ["train", "valid", "test"]


class DatasetRegistry:
    def __init__(self, config_path: Path | None = None):
        import os
        if config_path is None:
            env_path = os.environ.get("DATASETS_YAML")
            if env_path:
                config_path = Path(env_path)
            else:
                pkg_dir = Path(__file__).resolve().parent.parent
                config_path = pkg_dir / "config" / "datasets.yaml"
        self._config_path = Path(config_path)
        self._datasets: dict[str, DatasetConfig] = {}
        if self._config_path.exists():
            with open(self._config_path) as f:
                raw = yaml.safe_load(f)
            for key, cfg in raw.get("datasets", {}).items():
                self._datasets[key] = DatasetConfig(
                    key=key,
                    path=Path(cfg["path"]),
                    image_glob=cfg.get("image_glob", "**/*.jpg"),
                    label_format=cfg.get("label_format"),
                    label_glob=cfg.get("label_glob"),
                    component_labels=cfg.get("component_labels", False),
                    crop_to_components=cfg.get("crop_to_components", False),
                    description=cfg.get("description", ""),
                )

    def list_datasets(self) -> list[str]:
        return list(self._datasets.keys())

    def get(self, key: str) -> DatasetConfig | None:
        return self._datasets.get(key)

    def list_images(self, key: str, split: str = "train") -> list[Path]:
        cfg = self.get(key)
        if cfg is None:
            return []
        pattern = cfg.image_glob
        if "**/" in pattern:
            pattern = pattern.replace("**/", f"{split}/")
        return sorted(cfg.path.glob(pattern))

    def load_labels(self, image_path: Path, img_w: int = 640, img_h: int = 640) -> list[WireLine]:
        label_path = image_path.parent.parent / "labels" / image_path.with_suffix(".txt").name
        if not label_path.exists():
            return []
        return self._parse_labels(label_path, img_w, img_h)

    def _parse_labels(self, label_path: Path, img_w: int = 640, img_h: int = 640) -> list[WireLine]:
        lines = []
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 9:
                    continue
                try:
                    coords = [float(x) for x in parts[1:9]]
                    poly = np.array(
                        [[int(coords[i] * img_w), int(coords[i + 1] * img_h)]
                         for i in range(0, 8, 2)],
                        dtype=np.int32,
                    )
                    # Short-edge midpoint method: find the two shortest edges of the OBB,
                    # take their midpoints — this gives the true centerline for thin wires.
                    n_ = len(poly)
                    edges = [(i, (i + 1) % n_) for i in range(n_)]
                    el = [(np.linalg.norm(poly[a] - poly[b]), a, b) for a, b in edges]
                    el.sort(key=lambda x: x[0])
                    s1, s2 = el[0], el[1]
                    mid1 = (poly[s1[1]] + poly[s1[2]]) / 2
                    mid2 = (poly[s2[1]] + poly[s2[2]]) / 2
                    lines.append(WireLine(
                        p1=(int(mid1[0]), int(mid1[1])),
                        p2=(int(mid2[0]), int(mid2[1])),
                    ))
                except (ValueError, IndexError):
                    continue
        return lines

    def load_component_labels(self, image_path: Path) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]] | None:
        """Load HDC component labels for an image by filename prefix matching.
        
        Returns list of (class_id, polygon_points, bounding_box) or None if no match.
        """
        import cv2
        stem = image_path.stem  # e.g. "C100_D1_P1_jpg"

        hdc_cfg = self.get("hdc")
        if hdc_cfg is None:
            return None
        hdc_base = hdc_cfg.path

        # Try prefix matching against HDC label files
        label_path = None
        for split in HDC_SPLITS:
            label_dir = hdc_base / split / "labels"
            if not label_dir.exists():
                continue
            matches = sorted(label_dir.glob(f"{stem}.rf.*.txt"))
            if matches:
                label_path = matches[0]
                break
        
        if label_path is None or not label_path.exists():
            return None
        
        # Read image dimensions for normalization
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        h, w = img.shape
        
        # Parse YOLO-OBB labels (class_id x1 y1 x2 y2 x3 y3 x4 y4 normalized)
        components = []
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 9:
                    continue
                try:
                    cls_id = int(parts[0])
                    coords = [float(x) for x in parts[1:9]]
                    vertices = [
                        (int(coords[i] * w), int(coords[i + 1] * h))
                        for i in range(0, 8, 2)
                    ]
                    xs = [v[0] for v in vertices]
                    ys = [v[1] for v in vertices]
                    bbox = (min(xs), min(ys), max(xs), max(ys))
                    components.append((cls_id, vertices, bbox))
                except (ValueError, IndexError):
                    continue
        
        return components if components else None
