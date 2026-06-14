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

def find_roboflow_image(image_path: Path, hdc_base: Path | None = None) -> Path | None:
    """Find a Roboflow image by filename prefix (may be augmented).

    .. warning::
       Returns the FIRST match sorted by filename — may be an augmented version
       whose labels do NOT align with the original image.  For occlusion on
       original images, use :func:`find_exact_match_roboflow` instead.

    Returns an image path, or ``None`` if not found.
    """
    stem = image_path.stem  # e.g. "C100_D1_P1_jpg"
    if hdc_base is None:
        # Try to discover hdc_base from the label file path convention
        # Labels live under roboflow_test2/{split}/labels/
        for parent in [image_path.parent.parent, image_path.parent.parent.parent]:
            candidate = parent / "roboflow_test2"
            if candidate.exists():
                hdc_base = candidate
                break
        if hdc_base is None:
            return None

    for split in HDC_SPLITS:
        img_dir = hdc_base / split / "images"
        if not img_dir.exists():
            continue
        matches = sorted(img_dir.glob(f"{stem}.rf.*.jpg"))
        if matches:
            return matches[0]
    return None


def find_exact_match_roboflow(
    image_path: Path, hdc_base: Path | None = None
) -> tuple[Path, Path] | None:
    """Find the Roboflow version pixel-identical to ``image_path`` and its label.

    Roboflow duplicates each image under multiple ``.rf.<hash>`` filenames —
    some augmented, some untouched.  The untouched version's labels are in the
    **same coordinate space** as the original, so they can be used directly for
    occlusion without flip/rotation correction.

    CRITICAL (Jun 2026): Every Roboflow image has multiple versions.  The first
    match from ``find_roboflow_image()`` may be augmented — its labels will be
    in the wrong coordinate space for the original image, causing incorrect
    occlusion polygons.  Always prefer this function when loading component
    labels for occlusion on original images.

    Returns ``(roboflow_image_path, label_path)`` or ``None``.
    """
    import cv2

    stem = image_path.stem
    orig = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if orig is None:
        return None

    if hdc_base is None:
        for parent in [image_path.parent.parent, image_path.parent.parent.parent]:
            candidate = parent / "roboflow_test2"
            if candidate.exists():
                hdc_base = candidate
                break
        if hdc_base is None:
            return None

    for split in HDC_SPLITS:
        img_dir = hdc_base / split / "images"
        label_dir = hdc_base / split / "labels"
        if not img_dir.exists():
            continue
        for f in sorted(img_dir.glob(f"{stem}.rf.*.jpg")):
            rob = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if rob is not None and rob.shape == orig.shape:
                err = np.mean(np.abs(orig.astype(float) - rob.astype(float)))
                if err < 0.01:  # pixel-identical
                    label = label_dir / f"{f.stem}.txt"
                    if label.exists():
                        return (f, label)
    return None


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
        images = sorted(cfg.path.glob(pattern))
        # If label_glob is defined, filter to images that have at least one label
        if cfg.label_glob and cfg.label_glob.endswith("*.txt"):
            # Build set of stems that have labels
            label_dir = cfg.path
            lpattern = cfg.label_glob
            if "**/" in lpattern:
                lpattern = lpattern.replace("**/", f"{split}/")
            label_stems = {lp.stem for lp in label_dir.glob(lpattern)}
            # Match image stem to label stem
            # Images are like "C100_D1_P1_jpg.jpg", labels are like "C100_D1_P1_jpg.txt"
            filtered = [img for img in images if img.stem in label_stems]
            if filtered:
                return filtered
        return images

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

    def load_component_labels(
        self,
        image_path: Path,
        img_wh: tuple[int, int] | None = None,
    ) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]] | None:
        """Load HDC component labels for an image by filename prefix matching.

        Returns list of (class_id, polygon_points, bounding_box) or None if no match.
        Pass img_wh=(width, height) to skip re-decoding the image from disk just to
        denormalize the labels (the caller usually already has the decoded frame).
        """
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
        
        # Image dimensions for normalization — use the caller's if given, else decode.
        if img_wh is not None:
            w, h = img_wh
        else:
            import cv2
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

    def load_component_labels_aligned(
        self,
        image_path: Path,
        img_wh: tuple[int, int] | None = None,
    ) -> tuple[list, Path] | None:
        """Load HDC labels AND find the correctly-oriented Roboflow image.

        Returns ``(components, aligned_image_path)`` or ``None``.
        ``aligned_image_path`` is the Roboflow augmented version whose geometry
        matches the label coordinates — use this for occlusion / visualization
        instead of the original ``image_path``.  Falls back to ``image_path``
        when no augmented version exists (identical images).
        """
        components = self.load_component_labels(image_path, img_wh=img_wh)
        if components is None:
            return None

        hdc_cfg = self.get("hdc")
        hdc_base = hdc_cfg.path if hdc_cfg else None
        rob_path = find_roboflow_image(image_path, hdc_base)
        aligned = rob_path if rob_path is not None else image_path
        return (components, aligned)
