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
        pattern = cfg.image_glob.replace("**/", f"{split}/")
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
                    p1, p2, p3, p4 = poly
                    d13 = np.linalg.norm(p1 - p3)
                    d24 = np.linalg.norm(p2 - p4)
                    if d13 >= d24:
                        lines.append(WireLine(p1=tuple(p1), p2=tuple(p3)))
                    else:
                        lines.append(WireLine(p1=tuple(p2), p2=tuple(p4)))
                except (ValueError, IndexError):
                    continue
        return lines

    def load_component_labels(self, image_path: Path) -> list[dict[str, Any]] | None:
        return None
