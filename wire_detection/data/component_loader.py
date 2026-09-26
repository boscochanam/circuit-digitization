"""Component detection loader — single entry point for all component label sources.

Supports three sources (configurable via component_detection.source):
  - "model":        Trained YOLO26M-OBB model (single source of truth)
  - "ground_truth": GT annotation files (for benchmarking/evaluation)
  - "roboflow":     Legacy Roboflow pre-trained model (deprecated)

Usage:
    from wire_detection.data.component_loader import load_components

    # Uses config from defaults.yaml (component_detection.source)
    components = load_components(image_path)

    # Override source explicitly
    components = load_components(image_path, source="ground_truth")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from wire_detection.config.schema import ComponentDetectionConfig

log = logging.getLogger(__name__)

# Class names emitted by the shipped checkpoint, in ITS index order. Read from the
# checkpoint's own embedded ``model.names``, which is authoritative — the index order
# is NOT stable across retrains, so never assume an earlier ordering.
#   0 resistor, 1 terminal, 2 crossover, 3 capacitor, 4 diode, 5 transistor,
#   6 switch, 7 inductor, 8 voltage_source, 9 text, 10 junction, 11 gnd,
#   12 vss, 13 integrated_circuit, 14 operational_amplifier, 15 other
TRAINED_MODEL_CLASSES = {
    0: "resistor",
    1: "terminal",
    2: "crossover",
    3: "capacitor",
    4: "diode",
    5: "transistor",
    6: "switch",
    7: "inductor",
    8: "voltage_source",
    9: "text",
    10: "junction",
    11: "gnd",
    12: "vss",
    13: "integrated_circuit",
    14: "operational_amplifier",
    15: "other",
}

# Model class NAME -> representative id in the 58-class GT scheme (COMPONENT_TYPES)
# that the rest of the pipeline keys pin geometry and SPICE prefixes off of
# (PIN_DEFINITIONS / two_terminal / PREFIX_MAP). Where the model collapses several GT
# subtypes into one bucket we pick a representative with identical pin geometry.
MODEL_CLASS_NAME_TO_GT_CLASS = {
    "resistor": 37,                 # -> resistor
    "capacitor": 4,                 # -> capacitor-unpolarized
    "diode": 8,                     # -> diode
    "transistor": 47,               # -> transistor-BJT
    "inductor": 14,                 # -> inductor
    "voltage_source": 55,           # -> voltage-DC
    "integrated_circuit": 16,       # -> IC
    "operational_amplifier": 28,    # -> opamp
    "other": 51,                    # -> unknown
    "gnd": 13,                      # -> gnd
    "text": 44,                     # -> text
    "junction": 19,                 # -> junction
    "terminal": 43,                 # -> terminal
    "switch": 42,                   # -> switch
    "vss": 56,                      # -> vss
    "crossover": 5,                 # -> crossover
}
GT_CLASS_UNKNOWN = 51



def load_components(
    image_path: str | Path,
    source: Literal["model", "ground_truth", "roboflow"] | None = None,
    config: ComponentDetectionConfig | None = None,
    gt_label_path: str | Path | None = None,
    rob_label_path: str | Path | None = None,
    image_w: int | None = None,
    image_h: int | None = None,
) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]]:
    """Load component labels from the configured source.

    Args:
        image_path: Path to the input image.
        source: Override config source. If None, uses config.
        config: ComponentDetectionConfig. If None, loads from defaults.
        gt_label_path: Path to GT label file (required if source="ground_truth").
        rob_label_path: Path to Roboflow label file (required if source="roboflow").
        image_w: Image width for denormalizing GT labels.
        image_h: Image height for denormalizing GT labels.

    Returns:
        List of (class_id, polygon_points, bounding_box) tuples.
        bounding_box is (x1, y1, x2, y2) in pixel coordinates.

    Raises:
        FileNotFoundError: If the model file is missing (model source only).
        ValueError: If source is unknown or required args are missing.
    """
    if config is None:
        config = ComponentDetectionConfig()
    if source is None:
        source = config.source

    if source == "model":
        return _load_from_model(image_path, config)
    elif source == "ground_truth":
        if gt_label_path is None or image_w is None or image_h is None:
            raise ValueError(
                f"gt_label_path, image_w, image_h required for ground_truth source "
                f"(got gt_label_path={gt_label_path}, image_w={image_w}, image_h={image_h})"
            )
        return _load_from_gt(gt_label_path, image_w, image_h)
    elif source == "roboflow":
        if rob_label_path is None or image_w is None or image_h is None:
            raise ValueError(
                f"rob_label_path, image_w, image_h required for roboflow source "
                f"(got rob_label_path={rob_label_path}, image_w={image_w}, image_h={image_h})"
            )
        return _load_from_roboflow(rob_label_path, image_w, image_h)
    else:
        raise ValueError(
            f"Unknown component detection source: {source!r}. "
            f"Valid sources: 'model', 'ground_truth', 'roboflow'"
        )


def _load_from_model(
    image_path: str | Path,
    config: ComponentDetectionConfig,
) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]]:
    """Load components using the trained YOLO model.

    Returns empty list (with warning) for missing or unreadable images instead
    of raising exceptions.  Model-not-found still raises so callers can
    distinguish a missing model from a missing image.
    """
    from ultralytics import YOLO

    image_path = Path(image_path)

    # --- Validate image exists ---
    if not image_path.exists():
        log.warning("Image not found: %s — returning empty component list", image_path)
        return []
    if not image_path.is_file():
        log.warning("Image path is not a file: %s — returning empty component list", image_path)
        return []

    # --- Validate model exists (raise — callers must know) ---
    model_path = Path(config.model_path)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}\n"
            f"SHA256: d700b33f90191968af9f7f2798fff5e90a3f1ea473b811adc241bc570987264d"
        )

    try:
        model = YOLO(str(model_path))
    except Exception as exc:
        log.error("Failed to load YOLO model from %s: %s", model_path, exc)
        raise RuntimeError(f"Cannot load model {model_path}: {exc}") from exc

    # The checkpoint's own ``names`` are authoritative for its output indices. Map
    # them by NAME into the 58-class GT scheme the rest of the pipeline expects;
    # passing raw model indices through would mis-type nearly every component.
    model_names = getattr(model, "names", None) or TRAINED_MODEL_CLASSES
    idx_to_gt: dict[int, int] = {}
    unmapped: list[str] = []
    for idx, nm in model_names.items():
        key = str(nm).strip().lower()
        idx_to_gt[int(idx)] = MODEL_CLASS_NAME_TO_GT_CLASS.get(key, GT_CLASS_UNKNOWN)
        if key not in MODEL_CLASS_NAME_TO_GT_CLASS:
            unmapped.append(str(nm))
    if unmapped:
        log.warning(
            "Checkpoint classes not in the GT scheme, mapped to 'unknown': %s",
            sorted(set(unmapped)),
        )
    if len(idx_to_gt) != len(TRAINED_MODEL_CLASSES):
        log.warning(
            "Checkpoint exposes %d classes but TRAINED_MODEL_CLASSES lists %d",
            len(idx_to_gt), len(TRAINED_MODEL_CLASSES),
        )

    # --- Run inference ---
    try:
        results = model(str(image_path), task="obb", conf=config.confidence_threshold)
    except Exception as exc:
        log.warning(
            "Inference failed on %s: %s — returning empty component list",
            image_path, exc,
        )
        return []

    # --- Parse results ---
    components = []
    for result in results:
        if result.obb is None:
            continue
        for i in range(len(result.obb.cls)):
            raw_cls = int(result.obb.cls[i])
            # Translate the checkpoint's own index into the 58-class GT scheme.
            cls_id = idx_to_gt.get(raw_cls, GT_CLASS_UNKNOWN)
            # xyxy format: [x1, y1, x2, y2]
            bbox = result.obb.xyxy[i].tolist()
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            # Convert to polygon (4 corners from OBB)
            polygon = result.obb.xyxyxyxy[i].tolist()
            polygon_pts = [(int(p[0]), int(p[1])) for p in polygon]
            components.append((cls_id, polygon_pts, (x1, y1, x2, y2)))

    if not components:
        log.info("No components detected in %s", image_path.name)
    else:
        log.info("Model detected %d components in %s", len(components), image_path.name)
    return components


def _load_from_gt(
    label_path: str | Path,
    img_w: int,
    img_h: int,
) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]]:
    """Load components from ground truth YOLO-OBB label file.

    Returns empty list (with warning) for missing or unreadable labels.
    """
    label_path = Path(label_path)
    if not label_path.exists():
        log.warning("Label file not found: %s — returning empty component list", label_path)
        return []
    if not label_path.is_file():
        log.warning("Label path is not a file: %s — returning empty component list", label_path)
        return []

    try:
        components = []
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 9:
                    continue
                cls_id = int(parts[0])
                coords = [float(x) for x in parts[1:9]]
                # Denormalize from YOLO format
                xs = [int(coords[i] * img_w) for i in range(0, 8, 2)]
                ys = [int(coords[i + 1] * img_h) for i in range(0, 8, 2)]
                polygon = [(xs[i], ys[i]) for i in range(4)]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                components.append((cls_id, polygon, (x1, y1, x2, y2)))
    except (ValueError, UnicodeDecodeError) as exc:
        log.warning(
            "Failed to parse label file %s: %s — returning empty component list",
            label_path, exc,
        )
        return []

    log.debug("GT loaded %d components from %s", len(components), label_path.name)
    return components


def _load_from_roboflow(
    label_path: str | Path,
    img_w: int,
    img_h: int,
) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]]:
    """Load components from Roboflow label file (deprecated).

    NOTE: Roboflow uses non-standard class IDs (37, 14, 55, etc.).
    Prefer the trained model for consistent class mapping.
    """
    import warnings
    warnings.warn(
        "Roboflow component detection is deprecated. Use source='model' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _load_from_gt(label_path, img_w, img_h)


def get_class_name(cls_id: int, source: str = "model") -> str:
    """Get human-readable class name from class ID."""
    if source == "model":
        return TRAINED_MODEL_CLASSES.get(cls_id, f"unknown_{cls_id}")
    else:
        # GT/Roboflow use different class mappings
        return f"class_{cls_id}"
