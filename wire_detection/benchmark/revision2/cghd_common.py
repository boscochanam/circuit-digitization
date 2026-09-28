"""Shared helpers for the CGHD-annotation connectivity reference (revision 2, Access-2026-33821).

Data source: CGHD v12 (Thoma, Bayer et al., DFKI; Zenodo 10056817). The 257 samples that ship
labelme instance polygons (``drafter_*/instances/<stem>.json``) and binary stroke maps
(``drafter_*/segmentation/<stem>.jpg``). Nothing here reads our own connectivity labels.

Coordinate frames
  * CGHD frame: the EXIF-corrected original (cv2.imread default); instances + segmentation maps
    are in this frame (verified: json imageWidth/Height == EXIF-corrected size == seg-map size).
  * Benchmark frame: the 704x704 copies in labels_few_annot/images that our 31/134-image
    benchmarks use. They are STRETCHED resizes of the EXIF-corrected original, but ~45% of them
    additionally carry a dihedral transform (Roboflow flip/rot90 augmentation). The transform
    index k (see ``dihedral_norm``) is estimated per image in cghd_transform_probe.py from
    ink-map correlation and, where our component labels exist, confirmed by box IoU.

Not a pipeline module: nothing under wire_detection/core is modified.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import cv2
import numpy as np

CGHD_ROOT = Path(os.environ.get("CGHD_ROOT", os.path.expanduser("~/cghd_orig/cghd")))
BENCH_IMAGES = Path(os.environ.get("WIRE_GT_IMAGES",
                                   "/home/claw/workspace/ground_truth/labels_few_annot/images"))

# CGHD class name -> our 58-class Roboflow name (wire_detection.core.component_classes).
# Rule: '.' -> '-', plus the explicit renames below. Verified against our human component
# labels on the overlapping images (cghd_validate.py reports the class confusion).
_RENAME = {
    "diode.light_emitting": "diode-LED",
    "transistor.bjt": "transistor-BJT",
    "transistor.fet": "transistor-FET",
    "integrated_circuit": "IC",
    "integrated_circuit.ne555": "IC-NE555",
    "integrated_circuit.voltage_regulator": "IC-voltage-reg",
    "operational_amplifier": "opamp",
    "operational_amplifier.schmitt_trigger": "opamp-schmitt",
    "voltage.dc": "voltage-DC",
    "voltage.ac": "voltage-AC",
    "dirac": "diac",               # CGHD typo in a few files
    "inductor.coupled": "inductor",  # no coupled-inductor class in our 58-class set
    "block": "unknown",
}


def our_type_name(cghd_label: str) -> str:
    from wire_detection.core.component_classes import COMPONENT_TYPES
    names = set(COMPONENT_TYPES.values())
    n = _RENAME.get(cghd_label, cghd_label.replace(".", "-"))
    return n if n in names else "unknown"


def our_class_id(cghd_label: str) -> int:
    from wire_detection.core.component_classes import COMPONENT_TYPES
    inv = {v: k for k, v in COMPONENT_TYPES.items()}
    return inv[our_type_name(cghd_label)]


def is_electrical(cghd_label: str) -> bool:
    """Paper convention (build_net_gt.electrical_indices): SPICE-active prefixes only."""
    from wire_detection.core.component_classes import PREFIX_MAP, SIMULATABLE_PREFIXES
    return PREFIX_MAP.get(our_type_name(cghd_label)) in SIMULATABLE_PREFIXES


def list_samples() -> list[tuple[str, str]]:
    """[(drafter_dir, stem)] for every sample with an instance-polygon file, sorted."""
    out = []
    for f in sorted(glob.glob(str(CGHD_ROOT / "drafter_*" / "instances" / "*.json"))):
        out.append((Path(f).parts[-3], Path(f).stem))
    return sorted(out, key=lambda t: (int(t[0].split("_")[1]), t[1]))


def image_path(drafter: str, stem: str) -> Path:
    c = sorted(glob.glob(str(CGHD_ROOT / drafter / "images" / f"{stem}.*")))
    if not c:
        raise FileNotFoundError(f"no image for {drafter}/{stem}")
    return Path(c[0])


def load_gray(drafter: str, stem: str) -> np.ndarray:
    """EXIF-corrected grayscale original (cv2 applies EXIF orientation by default). Some files
    carry a wrong extension (e.g. PNG data named .jpg); fall back to PIL."""
    p = image_path(drafter, stem)
    g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if g is None:
        from PIL import Image, ImageOps
        g = np.array(ImageOps.exif_transpose(Image.open(p)).convert("L"))
    return g


def load_stroke_mask(drafter: str, stem: str) -> np.ndarray:
    """Binary stroke map as bool (True = stroke). Same threshold as CGHD segmentation.py."""
    c = sorted(glob.glob(str(CGHD_ROOT / drafter / "segmentation" / f"{stem}.*")))
    m = cv2.imread(c[0], cv2.IMREAD_GRAYSCALE)
    return m <= 127


def load_shapes(drafter: str, stem: str) -> tuple[list[dict], int, int]:
    j = json.load(open(CGHD_ROOT / drafter / "instances" / f"{stem}.json"))
    shapes = []
    for s in j["shapes"]:
        pts = np.asarray(s["points"], dtype=np.float64)
        if pts.ndim != 2 or len(pts) < 3:
            continue
        shapes.append({"label": s["label"], "points": pts})
    return shapes, int(j["imageWidth"]), int(j["imageHeight"])


# ---------------------------------------------------------------- dihedral frame mapping
def dihedral_array(a: np.ndarray, k: int) -> np.ndarray:
    """k in 0..7: np.rot90 k%4 times, then a horizontal flip if k>=4."""
    b = np.rot90(a, k % 4)
    return np.ascontiguousarray(b[:, ::-1] if k >= 4 else b)


def dihedral_norm(x, y, k):
    """Map normalized CGHD-frame coords to the normalized frame of dihedral_array(img, k)."""
    for _ in range(k % 4):
        x, y = y, 1 - x
    if k >= 4:
        x = 1 - x
    return x, y


# ---------------------------------------------------------------- component conversion
def shapes_to_components(shapes, sx: float, sy: float) -> list:
    """CGHD polygons -> our component tuples (cls_id, 4 OBB verts, AABB) at scale (sx, sy).
    OBB = cv2.minAreaRect of the (scaled) polygon; for the 4-point axis-aligned CGHD rectangles
    (the large majority) this is the rectangle itself."""
    comps = []
    for s in shapes:
        p = s["points"] * np.array([sx, sy])
        rect = cv2.minAreaRect(p.astype(np.float32))
        box = cv2.boxPoints(rect)
        verts = [(int(round(x)), int(round(y))) for x, y in box]
        x1, y1 = p.min(axis=0)
        x2, y2 = p.max(axis=0)
        comps.append((our_class_id(s["label"]), verts,
                      (int(np.floor(x1)), int(np.floor(y1)), int(np.ceil(x2)), int(np.ceil(y2)))))
    return comps
