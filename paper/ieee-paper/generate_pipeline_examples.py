from __future__ import annotations

from pathlib import Path

import base64
import cv2
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from wire_detection.api.routes.netlist import _run_preset_pipeline
from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.core.join_strategies import make_pins, run_strategy
from wire_detection.data.dataset import find_exact_match_roboflow

matplotlib.use("Agg")

REPO = Path(__file__).resolve().parents[2]
PAPER_DIR = Path(__file__).resolve().parent
FIG_DIR = PAPER_DIR / "figures" / "pipeline_examples"
GROUND_TRUTH_ROOT = (
    REPO
    / "ground_truth"
    / "chris_ground_truth"
    / "extracted_full"
    / "batchv2_annotations_2026_05_30_21_25_03_ultralytics_yolo_oriented_bounding_boxes_1.0"
    / "task_2293822_annotations_2026_05_30_21_25_03_ultralytics yolo oriented bounding boxes 1.0"
)

CASES = [
    ("C84_D1_P2", "C84-D1-P2-jpg.png"),
]

COLORS = {
    "ink": "#1E2F3F",
    "muted": "#6A7D8F",
    "panel": "#FBFAF7",
    "panel_edge": "#D6D1C8",
    "header": "#243746",
    "wire": "#A95E52",
    "component": "#6D8B74",
    "pin_on": "#2F5D73",
    "pin_off": "#C47B47",
}

SKIP_PIN_TYPES = {
    "junction",
    "terminal",
    "gnd",
    "crossover",
    "vss",
    "text",
    "unknown",
    "mechanical",
    "optical",
    "probe",
    "probe-current",
    "probe-voltage",
}
SKIP_PIN_IDS = {cid for cid, name in COMPONENT_TYPES.items() if name in SKIP_PIN_TYPES}


def draw_polygon(image: np.ndarray, vertices: list[tuple[int, int]], color_bgr: tuple[int, int, int], thickness: int = 1) -> None:
    pts = np.array(vertices, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(image, [pts], True, color_bgr, thickness, cv2.LINE_AA)


def load_case_components(image_path: Path) -> tuple[np.ndarray, list]:
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(image_path)
    exact = find_exact_match_roboflow(image_path, REPO / "roboflow_test2")
    if exact is None:
        raise RuntimeError(f"No exact-match HDC label found for {image_path.name}")
    _, label_path = exact
    h, w = gray.shape
    components = ref.parse_components(label_path, w, h)
    return gray, components


def build_stages(case_id: str) -> tuple[dict[str, np.ndarray], dict[str, int]]:
    image_path = GROUND_TRUTH_ROOT / "images" / "train" / f"{case_id}_jpg.jpg"
    gray, components = load_case_components(image_path)
    result = _run_preset_pipeline(gray, "best_candidate_v4", {}, image_path=str(image_path))

    stages: dict[str, np.ndarray] = {}
    stages["original"] = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    def decode_payload(key: str) -> np.ndarray:
        payload = result.get(key)
        if not payload:
            raise RuntimeError(f"Missing {key} payload for {case_id}")
        raw = base64.b64decode(payload)
        arr = np.frombuffer(raw, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if decoded is None:
            raise RuntimeError(f"Could not decode {key} payload for {case_id}")
        return decoded

    occluded = decode_payload("overlay")
    binary = decode_payload("threshold")
    closed = decode_payload("dilated")
    lines = result.get("lines", [])
    pins = make_pins(lines, components)
    _, net = run_strategy("degree_budget", lines, components, std_pins=pins)

    stages["occluded"] = cv2.cvtColor(occluded, cv2.COLOR_GRAY2RGB)
    stages["binary"] = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
    stages["closed"] = cv2.cvtColor(closed, cv2.COLOR_GRAY2RGB)

    wire_overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    for cls_id, vertices, _ in components:
        if cls_id not in SKIP_PIN_IDS:
            draw_polygon(wire_overlay, vertices, (116, 139, 109), 1)
    for (x1, y1), (x2, y2) in lines:
        cv2.line(wire_overlay, (x1, y1), (x2, y2), (82, 94, 169), 2, cv2.LINE_AA)
    stages["wire_overlay"] = wire_overlay

    join_overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    join_overlay = np.clip(join_overlay * 0.86 + 12, 0, 255).astype(np.uint8)
    for cls_id, vertices, _ in components:
        if cls_id not in SKIP_PIN_IDS:
            draw_polygon(join_overlay, vertices, (116, 139, 109), 1)
    attached_pins: set[tuple[int, int]] = set()
    if net is not None:
        for node in net.nodes:
            for pin in node.pins:
                attached_pins.add((pin.component_idx, pin.pin_idx))
    for pin in pins:
        if pin.component_idx >= len(components):
            continue
        cls_id = components[pin.component_idx][0]
        if cls_id in SKIP_PIN_IDS:
            continue
        px = int(pin.x)
        py = int(pin.y)
        attached = (pin.component_idx, pin.pin_idx) in attached_pins
        fill = (115, 93, 47) if attached else (71, 123, 196)
        cv2.circle(join_overlay, (px, py), 4, fill, -1, cv2.LINE_AA)
        cv2.circle(join_overlay, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)
    stages["join_overlay"] = join_overlay

    meta = {
        "wires": len(lines),
        "components": sum(1 for cls_id, _, _ in components if cls_id not in SKIP_PIN_IDS),
        "nets": len([node for node in getattr(net, "nodes", []) if node.wires]) if net is not None else 0,
    }
    return stages, meta


def style_panel(ax: plt.Axes, image: np.ndarray, title: str, subtitle: str | None = None) -> None:
    ax.imshow(image, cmap=None if image.ndim == 3 else "gray")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.0)
        spine.set_edgecolor(COLORS["panel_edge"])
    ax.set_facecolor(COLORS["panel"])
    ax.set_title(title, fontsize=9.5, color=COLORS["ink"], pad=5)
    if subtitle:
        ax.text(0.5, -0.08, subtitle, transform=ax.transAxes, ha="center", va="top", fontsize=7.5, color=COLORS["muted"])


def save_case(case_id: str, out_name: str) -> None:
    stages, meta = build_stages(case_id)
    fig, axes = plt.subplots(1, 4, figsize=(12.8, 3.9), dpi=450)
    fig.patch.set_facecolor("white")

    panels = [
        ("original", "(a) Input scan", None),
        ("occluded", "(b) Component priors", None),
        ("wire_overlay", "(c) Detected wire fragments", None),
        ("join_overlay", "(d) NetGuard recovered joins", None),
    ]
    for ax, (key, title, subtitle) in zip(axes.flat, panels):
        style_panel(ax, stages[key], title, subtitle)

    fig.text(0.05, 0.965, case_id.replace("_", "-"), fontsize=12.5, color=COLORS["ink"], weight="semibold")
    fig.text(
        0.05,
        0.925,
        "Anchor-Guided PCA detection followed by NetGuard",
        fontsize=9.1,
        color=COLORS["muted"],
    )
    fig.text(
        0.985,
        0.925,
        f"{meta['wires']} fragments | {meta['nets']} nets | {meta['components']} components",
        fontsize=8.9,
        color=COLORS["muted"],
        ha="right",
    )
    fig.subplots_adjust(left=0.045, right=0.99, top=0.86, bottom=0.1, wspace=0.08)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / out_name, bbox_inches="tight", dpi=400)
    plt.close(fig)


def main() -> None:
    for case_id, out_name in CASES:
        save_case(case_id, out_name)


if __name__ == "__main__":
    main()
