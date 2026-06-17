from __future__ import annotations

import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np

from wire_detection.benchmark import experiment_harness as harness
from wire_detection.benchmark import reference_pipeline as ref


ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = ROOT / "paper"
FIG_DIR = PAPER_DIR / "figures"
TABLE_DIR = PAPER_DIR / "tables"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_comparison_chart() -> None:
    rows = [
        ("Reference baseline", 0.7066, 0.6169, 0.8267),
        ("Refined classical pipeline", 0.7492, 0.7236, 0.7767),
        ("Topology guided skeleton graph", 0.7830, 0.7411, 0.8300),
        ("Hybrid recovery method", 0.8215, 0.7275, 0.9433),
    ]

    labels = [
        "Reference\nbaseline",
        "Refined\nclassical",
        "Topology guided\nskeleton",
        "Hybrid\nrecovery",
    ]
    f1s = [r[1] for r in rows]
    ps = [r[2] for r in rows]
    rs = [r[3] for r in rows]

    x = np.arange(len(labels))
    width = 0.24
    plt.figure(figsize=(8.8, 4.8))
    plt.bar(x - width, f1s, width=width, color="#0f766e", label="F1")
    plt.bar(x, ps, width=width, color="#7c3aed", label="Precision")
    plt.bar(x + width, rs, width=width, color="#ea580c", label="Recall")
    plt.ylim(0.3, 1.0)
    plt.xticks(x, labels, rotation=0, ha="center")
    plt.ylabel("Score")
    plt.title("Benchmark comparison on 23 hand drawn schematic images")
    plt.grid(axis="y", alpha=0.2)
    plt.legend(frameon=False, ncol=3, loc="upper left")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "benchmark_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()


def annotate_panel(img: np.ndarray, title: str, subtitle: str) -> np.ndarray:
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    banner = np.full((54, img.shape[1], 3), 255, dtype=np.uint8)
    cv2.putText(banner, title, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (25, 25, 25), 1, cv2.LINE_AA)
    cv2.putText(banner, subtitle, (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (90, 90, 90), 1, cv2.LINE_AA)
    return np.vstack([banner, img])


def resize_panel(img: np.ndarray, width: int = 300) -> np.ndarray:
    h, w = img.shape[:2]
    scale = width / float(w)
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(img, (width, new_h), interpolation=cv2.INTER_AREA)


def colorize_mask(mask: np.ndarray) -> np.ndarray:
    mask_u8 = mask.astype(np.uint8)
    if mask_u8.ndim == 2:
        return cv2.cvtColor(mask_u8, cv2.COLOR_GRAY2BGR)
    return mask_u8


def make_qualitative_figure() -> None:
    summary = load_json(ROOT / "output" / "benchmark_experiments" / "hybrid_gaussian_fp_guard_b" / "summary.json")
    summary_by_name = {row["image"]: row for row in summary["images"]}
    cfg = harness.ExperimentConfig(**summary["config"])
    secondary_cfg = harness.secondary_recovery_config(cfg)

    selections = [
        ("C110_D1_P2", "Strong success", "Perfect recovery with clean topology"),
        ("C101_D1_P1", "Hard recall case", "Thin traces remain partially missed"),
        ("C105_D2_P4", "Redundancy heavy case", "Dense structure still induces extra segments"),
    ]

    rows = []
    for image_name, label, note in selections:
        src = cv2.imread(str(ROOT / "labels_few_annot" / "images" / f"{image_name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        ov = cv2.imread(str(ROOT / "output" / "benchmark_experiments" / "hybrid_gaussian_fp_guard_b" / "overlays" / f"{image_name}.png"))
        hdc_label = ref.find_hdc_label(image_name, src)
        components = ref.parse_components(hdc_label, src.shape[1], src.shape[0]) if hdc_label else []
        occluded = harness.build_component_mask(src, components, cfg.occlusion_margin)
        cropped, ox, oy = harness.crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = harness.shift_components(components, ox, oy)

        primary_masks = harness.build_binary_masks(harness.normalize_image(cropped, cfg.normalize_mode), cfg)
        primary_fused, _ = harness.fuse_masks(primary_masks, cfg.threshold_vote if cfg.threshold_fusion_enabled else 1)

        recovery_masks = harness.build_binary_masks(harness.normalize_image(cropped, secondary_cfg.normalize_mode), secondary_cfg)
        recovery_fused, _ = harness.fuse_masks(
            recovery_masks,
            secondary_cfg.threshold_vote if secondary_cfg.threshold_fusion_enabled else 1,
        )

        comp_canvas = cv2.cvtColor(cropped, cv2.COLOR_GRAY2BGR)
        for _, poly, _ in local_components:
            cv2.polylines(comp_canvas, [np.array(poly, dtype=np.int32)], True, (80, 120, 230), 2, cv2.LINE_AA)

        result = summary_by_name[image_name]
        subtitle = f"F1={result['f1']:.3f}  TP={result['tp']}  FP={result['fp']}  FN={result['fn']}"
        panels = [
            annotate_panel(resize_panel(src), f"{image_name}  input", label),
            annotate_panel(resize_panel(comp_canvas), "ROI after occlusion", "cropped circuit region"),
            annotate_panel(resize_panel(colorize_mask(primary_fused)), "Conservative mask", "Sauvola evidence"),
            annotate_panel(resize_panel(colorize_mask(recovery_fused)), "Recovery mask", "adaptive Gaussian"),
            annotate_panel(resize_panel(ov), "Final overlay", subtitle),
        ]
        target_h = max(panel.shape[0] for panel in panels)
        aligned = []
        for panel in panels:
            if panel.shape[0] != target_h:
                panel = cv2.copyMakeBorder(panel, 0, target_h - panel.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            aligned.append(panel)
        gap = np.full((target_h, 14, 3), 255, dtype=np.uint8)
        row = aligned[0]
        for panel in aligned[1:]:
            row = np.hstack([row, gap, panel])
        footer = np.full((30, row.shape[1], 3), 255, dtype=np.uint8)
        cv2.putText(footer, note, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (90, 90, 90), 1, cv2.LINE_AA)
        rows.append(np.vstack([row, footer]))

    width = max(r.shape[1] for r in rows)
    padded = []
    for row in rows:
        if row.shape[1] < width:
            row = cv2.copyMakeBorder(row, 0, 0, 0, width - row.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
        padded.append(row)
    sep = np.full((18, width, 3), 255, dtype=np.uint8)
    canvas = padded[0]
    for row in padded[1:]:
        canvas = np.vstack([canvas, sep, row])
    cv2.imwrite(str(FIG_DIR / "qualitative_cases.png"), canvas)


def write_tables() -> None:
    def tex_escape(text: str) -> str:
        return text.replace("_", r"\_")

    baseline = [
        ("Reference baseline", "0.7066", "0.6169", "0.8267", "248", "70", "52", "84"),
        ("Refined classical pipeline", "0.7492", "0.7236", "0.7767", "233", "43", "67", "46"),
        ("Topology guided skeleton graph", "0.7830", "0.7411", "0.8300", "249", "48", "51", "39"),
        ("Hybrid recovery method", "0.8215", "0.7275", "0.9433", "283", "63", "17", "43"),
    ]
    comparison = [
        r"{\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{p{5.0cm}ccccccc}",
        r"\toprule",
        r"Method & F1 & Precision & Recall & TP & FP & FN & Red \\",
        r"\midrule",
    ]
    for row in baseline:
        comparison.append(" {} & {} & {} & {} & {} & {} & {} & {} \\\\".format(*row))
    comparison.extend([r"\bottomrule", r"\end{tabular}", r"}"])
    (TABLE_DIR / "main_comparison.tex").write_text("\n".join(comparison), encoding="utf-8")

    summary_v7 = load_json(ROOT / "output" / "benchmark_experiments" / "hybrid_gaussian_fp_guard_b" / "summary.json")
    appendix = [
        r"{\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{p{2.6cm}ccccc p{4.8cm}}",
        r"\toprule",
        r"Image & F1 & TP & FP & FN & Red & Tags \\",
        r"\midrule",
    ]
    for row in summary_v7["images"]:
        tags = ", ".join(row["tags"]) if row["tags"] else "--"
        appendix.append(
            f" {tex_escape(row['image'])} & {row['f1']:.3f} & {row['tp']} & {row['fp']} & {row['fn']} & {row['red']} & {tex_escape(tags)} \\\\"
        )
    appendix.extend([r"\bottomrule", r"\end{tabular}", r"}"])
    (TABLE_DIR / "appendix_per_image.tex").write_text("\n".join(appendix), encoding="utf-8")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    make_comparison_chart()
    make_qualitative_figure()
    write_tables()


if __name__ == "__main__":
    main()
