"""Startup helpers for the API server."""
from pathlib import Path

import yaml

from wire_detection.data.dataset import DatasetRegistry


def load_default_config() -> dict:
    """Load pipeline config from defaults.yaml."""
    pkg_dir = Path(__file__).resolve().parent.parent.parent
    defaults_path = pkg_dir / "config" / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            return yaml.safe_load(f)
    return {
        "stages": ["crop", "mask", "threshold", "invert", "close", "ccl", "contour_extract", "dedup"],
        "stage_params": {
            "crop": {"padding": 10},
            "mask": {"fill_value": 255, "occlusion_margin": 0.15},
            "threshold": {"mode": "sauvola", "k": 0.30, "window": 51},
            "close": {"kernel_size": 3, "shape": "ellipse"},
            "ccl": {"min_area": 20},
            "dedup": {"angle_thresh": 10, "dist_thresh": 18},
        },
    }


def ensure_synthetic_data(registry: DatasetRegistry) -> None:
    """Generate synthetic dataset if needed."""
    cfg = registry.get("synthetic")
    if cfg is None:
        return
    cfg.path.mkdir(parents=True, exist_ok=True)
    existing = registry.list_images("synthetic")
    if len(existing) >= 50:
        return
    from wire_detection.sdg.generator import SDG, SDGConfig
    parts = cfg.image_glob.split("/")
    try:
        img_idx = parts.index("images")
        subdir = "/".join(parts[:img_idx])
        output_dir = cfg.path / subdir if subdir else cfg.path
    except ValueError:
        output_dir = cfg.path
    print(f"Generating synthetic dataset at {output_dir}...")
    sdg = SDG(SDGConfig(
        num_images=50, seed=42, image_size=(640, 640),
        output_dir=output_dir, label_format=cfg.label_format or "lines",
        components_count=(4, 8), components_size=(50, 130),
    ))
    sdg.generate()
    print("Synthetic dataset generated.")


def log_dataset_inventory(registry: DatasetRegistry) -> None:
    """Print dataset inventory on startup."""
    print("Dataset inventory:")
    for key in registry.list_datasets():
        cfg = registry.get(key)
        n = len(registry.list_images(key))
        path = cfg.path if cfg else "?"
        print(f"  {key}: {n} images ({path})")
        if key == "gt_labels" and n == 0:
            print(
                "  WARNING: gt_labels is empty. Mount your labels_few_annot folder via "
                "GT_LABELS_PATH in .env (see .env.example)."
            )
