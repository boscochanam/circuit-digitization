from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from wire_detection.data.cghd_subset import load_cghd_class_map, polygon_to_yolo_obb


REPO_ROOT = Path(__file__).resolve().parents[2]
CGHD_ROOT = REPO_ROOT / "cghd1152"
GT_LABELS = REPO_ROOT / "labels_few_annot" / "labels" / "train" / "manually_verified_no_background_data" / "images"
GT_IMAGES = REPO_ROOT / "labels_few_annot" / "images"
OUT_BASE = REPO_ROOT / "roboflow_test2" / "train"


def export_yolo_obb(labels: list[tuple[int, list[float]]], path: Path) -> None:
    lines = [
        " ".join([str(class_id)] + [f"{value:.6f}" for value in coords])
        for class_id, coords in labels
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def find_instance_json(image_stem: str) -> Path | None:
    matches = list(CGHD_ROOT.glob(f"drafter_*/instances/{image_stem}.json"))
    return matches[0] if matches else None


def find_annotation_xml(image_stem: str) -> Path | None:
    matches = list(CGHD_ROOT.glob(f"drafter_*/annotations/{image_stem}.xml"))
    return matches[0] if matches else None


def rotated_box_points(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    rotation_deg: float,
) -> list[list[float]]:
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    half_w = max((xmax - xmin) / 2.0, 1.0)
    half_h = max((ymax - ymin) / 2.0, 1.0)
    theta = math.radians(rotation_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    corners = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ]
    points: list[list[float]] = []
    for dx, dy in corners:
        x = cx + dx * cos_t - dy * sin_t
        y = cy + dx * sin_t + dy * cos_t
        points.append([x, y])
    return points


def load_xml_labels(xml_path: Path, class_map: dict[str, int]) -> tuple[int, int, list[tuple[int, list[float]]]]:
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    size = root.find("size")
    width = int(size.findtext("width", default="0")) if size is not None else 0
    height = int(size.findtext("height", default="0")) if size is not None else 0
    labels: list[tuple[int, list[float]]] = []

    for obj in root.findall("object"):
        label = obj.findtext("name")
        bbox = obj.find("bndbox")
        if label not in class_map or bbox is None:
            continue
        xmin = float(bbox.findtext("xmin", default="0"))
        ymin = float(bbox.findtext("ymin", default="0"))
        xmax = float(bbox.findtext("xmax", default="0"))
        ymax = float(bbox.findtext("ymax", default="0"))
        rotation = float(bbox.findtext("rotation", default="0"))
        points = rotated_box_points(xmin, ymin, xmax, ymax, rotation)
        labels.append((class_map[label], polygon_to_yolo_obb(points, width, height)))

    return width, height, labels


def main() -> None:
    class_map = load_cghd_class_map(CGHD_ROOT)
    out_images = OUT_BASE / "images"
    out_labels = OUT_BASE / "labels"
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)

    summary: list[dict[str, object]] = []

    for gt_label_path in sorted(GT_LABELS.glob("*_jpg.txt")):
        image_stem = gt_label_path.stem.replace("_jpg", "")
        gt_image_path = GT_IMAGES / f"{image_stem}_jpg.jpg"
        inst_path = find_instance_json(image_stem)
        xml_path = find_annotation_xml(image_stem)
        if (inst_path is None and xml_path is None) or not gt_image_path.exists():
            summary.append({"image": image_stem, "status": "missing_source"})
            continue

        labels: list[tuple[int, list[float]]]
        if inst_path is not None:
            data = json.loads(inst_path.read_text(encoding="utf-8"))
            image_info = data.get("image", {})
            width = int(image_info.get("width", 0))
            height = int(image_info.get("height", 0))
            labels = []

            for shape in data.get("shapes", []):
                label = shape.get("label")
                points = shape.get("points") or []
                if label not in class_map or len(points) < 3:
                    continue
                labels.append((class_map[label], polygon_to_yolo_obb(points, width, height)))
            source = inst_path
        else:
            width, height, labels = load_xml_labels(xml_path, class_map)
            source = xml_path

        out_image_path = out_images / gt_image_path.name
        out_label_path = out_labels / f"{gt_image_path.stem}.txt"
        out_image_path.write_bytes(gt_image_path.read_bytes())
        export_yolo_obb(labels, out_label_path)

        summary.append(
            {
                "image": image_stem,
                "status": "ok",
                "num_components": len(labels),
                "instance_source": str(source.relative_to(REPO_ROOT)),
            }
        )

    summary_path = REPO_ROOT / "data" / "local_reference_hdc_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    ok = sum(1 for row in summary if row["status"] == "ok")
    print(f"Built local HDC stand-in for {ok} benchmark images at {OUT_BASE}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
