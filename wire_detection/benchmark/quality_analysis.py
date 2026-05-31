from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wire_detection.vlm.vlm_classifier import classify_programmatic, compute_quality_scores


@dataclass
class BenchmarkQualityRow:
    image: str
    path: str
    ref_f1: float
    candidate_f1: float
    delta_f1: float
    tp: int
    fp: int
    fn: int
    red: int
    mean: float
    contrast: float
    grid_score: float
    shadow_score: float
    composite: float
    programmatic_type: str
    programmatic_reason: str
    vlm_paper_type: str | None
    vlm_verdict: str | None
    vlm_reason: str | None
    tags: list[str]


def parse_reference_run(path: Path) -> dict[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-16", errors="replace").splitlines()
    rows: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"^(C\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+(\d+)$"
    )
    for line in text:
        match = pattern.match(line.strip())
        if not match:
            continue
        image, gt, detected, tp, fp, fn, red, f1, comps = match.groups()
        rows[image] = {
            "gt": int(gt),
            "detected": int(detected),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "red": int(red),
            "f1": float(f1),
            "comps": int(comps),
        }
    return rows


def find_image(cghd_root: Path, image_name: str) -> Path:
    matches = list(cghd_root.glob(f"**/{image_name}.jpg")) + list(
        cghd_root.glob(f"**/{image_name}.jpeg")
    )
    if not matches:
        raise FileNotFoundError(f"Could not find CGHD image for {image_name}")
    return matches[0]


def corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    x = np.array(xs, dtype=float)
    y = np.array(ys, dtype=float)
    value = np.corrcoef(x, y)[0, 1]
    if np.isnan(value):
        return 0.0
    return float(value)


def mean_f1(rows: list[BenchmarkQualityRow]) -> float:
    if not rows:
        return 0.0
    return float(np.mean([row.candidate_f1 for row in rows]))


def build_report(
    candidate_summary_path: Path,
    reference_run_path: Path,
    cghd_root: Path,
    reclassified_path: Path | None,
) -> dict[str, Any]:
    candidate = json.loads(candidate_summary_path.read_text())
    reference = parse_reference_run(reference_run_path)
    reclassified_by_name: dict[str, dict[str, Any]] = {}
    if reclassified_path and reclassified_path.exists():
        reclassified = json.loads(reclassified_path.read_text())
        reclassified_by_name = {Path(r["filename"]).stem: r for r in reclassified}

    rows: list[BenchmarkQualityRow] = []
    for item in candidate["images"]:
        image_name = item["image"]
        image_path = find_image(cghd_root, image_name)
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise RuntimeError(f"Could not read {image_path}")
        scores = compute_quality_scores(gray)
        programmatic_type, programmatic_reason = classify_programmatic(scores)
        vlm = reclassified_by_name.get(image_name)
        ref = reference[image_name]
        rows.append(
            BenchmarkQualityRow(
                image=image_name,
                path=str(image_path),
                ref_f1=ref["f1"],
                candidate_f1=float(item["f1"]),
                delta_f1=float(item["f1"]) - ref["f1"],
                tp=int(item["tp"]),
                fp=int(item["fp"]),
                fn=int(item["fn"]),
                red=int(item["red"]),
                mean=float(scores.mean),
                contrast=float(scores.contrast),
                grid_score=float(scores.grid_score),
                shadow_score=float(scores.shadow_score),
                composite=float(scores.composite),
                programmatic_type=programmatic_type,
                programmatic_reason=programmatic_reason,
                vlm_paper_type=vlm["paper_type"] if vlm else None,
                vlm_verdict=vlm["verdict"] if vlm else None,
                vlm_reason=vlm["reason"] if vlm else None,
                tags=list(item.get("tags", [])),
            )
        )

    metric_correlations = {
        "mean_vs_f1": corr([r.mean for r in rows], [r.candidate_f1 for r in rows]),
        "contrast_vs_f1": corr([r.contrast for r in rows], [r.candidate_f1 for r in rows]),
        "grid_vs_f1": corr([r.grid_score for r in rows], [r.candidate_f1 for r in rows]),
        "shadow_vs_f1": corr([r.shadow_score for r in rows], [r.candidate_f1 for r in rows]),
        "composite_vs_f1": corr([r.composite for r in rows], [r.candidate_f1 for r in rows]),
        "mean_vs_delta": corr([r.mean for r in rows], [r.delta_f1 for r in rows]),
        "contrast_vs_delta": corr([r.contrast for r in rows], [r.delta_f1 for r in rows]),
        "grid_vs_delta": corr([r.grid_score for r in rows], [r.delta_f1 for r in rows]),
        "shadow_vs_delta": corr([r.shadow_score for r in rows], [r.delta_f1 for r in rows]),
        "composite_vs_delta": corr([r.composite for r in rows], [r.delta_f1 for r in rows]),
    }

    hard_rows = [r for r in rows if "hard_case" in r.tags]
    redundancy_rows = [r for r in rows if "redundancy_heavy" in r.tags]
    shadow_rows = [r for r in rows if r.programmatic_type == "shadow_issue"]
    grid_rows = [r for r in rows if r.programmatic_type == "likely_grid"]
    unknown_rows = [r for r in rows if r.programmatic_type == "unknown"]

    overlap_rows = [r for r in rows if r.vlm_paper_type is not None]

    report = {
        "candidate_name": candidate["config"]["name"],
        "candidate_global_f1": candidate["global_f1"],
        "reference_global_f1": 0.7066,
        "candidate_minus_reference": candidate["global_f1"] - 0.7066,
        "benchmark_size": len(rows),
        "vlm_overlap_count": len(overlap_rows),
        "programmatic_type_counts": dict(Counter(r.programmatic_type for r in rows)),
        "tag_counts": dict(Counter(tag for r in rows for tag in r.tags)),
        "correlations": metric_correlations,
        "group_means": {
            "hard_case_mean_f1": mean_f1(hard_rows),
            "redundancy_heavy_mean_f1": mean_f1(redundancy_rows),
            "shadow_issue_mean_f1": mean_f1(shadow_rows),
            "likely_grid_mean_f1": mean_f1(grid_rows),
            "unknown_mean_f1": mean_f1(unknown_rows),
        },
        "worst_images": [asdict(r) for r in sorted(rows, key=lambda row: row.candidate_f1)[:8]],
        "best_images": [asdict(r) for r in sorted(rows, key=lambda row: row.candidate_f1, reverse=True)[:8]],
        "vlm_overlap": [asdict(r) for r in overlap_rows],
        "rows": [asdict(r) for r in rows],
    }
    return report


def write_markdown(report: dict[str, Any], output_path: Path) -> None:
    worst = report["worst_images"]
    best = report["best_images"]
    corr_map = report["correlations"]
    group_means = report["group_means"]
    programmatic_counts = report["programmatic_type_counts"]

    lines = [
        "# Benchmark Quality Bridge",
        "",
        "## Summary",
        "",
        f"- Candidate method: `{report['candidate_name']}`",
        f"- Candidate F1: `{report['candidate_global_f1']:.4f}`",
        f"- Reference F1: `{report['reference_global_f1']:.4f}`",
        f"- Improvement: `{report['candidate_minus_reference']:+.4f}`",
        f"- Benchmark images analyzed: `{report['benchmark_size']}`",
        f"- Benchmark images with checked-in VLM labels: `{report['vlm_overlap_count']}`",
        "",
        "## Main Finding",
        "",
        "The CGHD quality-audit signal does not strongly explain wire benchmark performance on its own.",
        "Programmatic quality metrics show only weak-to-moderate correlation with F1, and some of the hardest wire cases are visually clean according to the quality audit heuristics.",
        "",
        "## Correlations",
        "",
        f"- `contrast` vs candidate F1: `{corr_map['contrast_vs_f1']:.3f}`",
        f"- `composite` vs candidate F1: `{corr_map['composite_vs_f1']:.3f}`",
        f"- `mean brightness` vs candidate F1: `{corr_map['mean_vs_f1']:.3f}`",
        f"- `grid score` vs candidate F1: `{corr_map['grid_vs_f1']:.3f}`",
        f"- `shadow score` vs candidate F1: `{corr_map['shadow_vs_f1']:.3f}`",
        f"- `contrast` vs improvement over reference: `{corr_map['contrast_vs_delta']:.3f}`",
        f"- `grid score` vs improvement over reference: `{corr_map['grid_vs_delta']:.3f}`",
        "",
        "## Programmatic Quality Types",
        "",
    ]
    for key, value in sorted(programmatic_counts.items()):
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(
        [
            "",
            "## Group Means",
            "",
            f"- Hard-case mean F1: `{group_means['hard_case_mean_f1']:.4f}`",
            f"- Redundancy-heavy mean F1: `{group_means['redundancy_heavy_mean_f1']:.4f}`",
            f"- `shadow_issue` mean F1: `{group_means['shadow_issue_mean_f1']:.4f}`",
            f"- `likely_grid` mean F1: `{group_means['likely_grid_mean_f1']:.4f}`",
            f"- `unknown` programmatic type mean F1: `{group_means['unknown_mean_f1']:.4f}`",
            "",
            "## Worst Images",
            "",
            "| Image | Candidate F1 | Ref F1 | Delta | Programmatic Type | Composite | Grid | Shadow | Tags |",
            "|---|---:|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for row in worst:
        lines.append(
            f"| `{row['image']}` | `{row['candidate_f1']:.4f}` | `{row['ref_f1']:.4f}` | `{row['delta_f1']:+.4f}` | "
            f"`{row['programmatic_type']}` | `{row['composite']:.3f}` | `{row['grid_score']:.1f}` | `{row['shadow_score']:.1f}` | "
            f"`{', '.join(row['tags'])}` |"
        )

    lines.extend(
        [
            "",
            "## Best Images",
            "",
            "| Image | Candidate F1 | Programmatic Type | Composite | Grid | Shadow |",
            "|---|---:|---|---:|---:|---:|",
        ]
    )
    for row in best:
        lines.append(
            f"| `{row['image']}` | `{row['candidate_f1']:.4f}` | `{row['programmatic_type']}` | "
            f"`{row['composite']:.3f}` | `{row['grid_score']:.1f}` | `{row['shadow_score']:.1f}` |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The quality-audit method is useful for dataset curation, but it does not appear sufficient as an explanation for benchmark wire failures.",
            "- The hardest benchmark failures are still primarily method failures: faint traces, fragmentation, and redundancy near dense components.",
            "- The audit is strongest as supporting methodology: dataset screening, benchmark stratification, and a limitations analysis.",
            "- The audit is not strong enough, from this benchmark alone, to replace the main paper claim with a quality-driven claim.",
            "",
            "## Recommended Paper Use",
            "",
            "- Include the VLM/programmatic audit as a supplementary data-quality and curation method if you want a broader methodological contribution.",
            "- Keep the main paper centered on wire extraction unless you expand the quality study beyond this 23-image benchmark and show stronger predictive value.",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge CGHD quality audit signals to benchmark wire performance")
    parser.add_argument(
        "--candidate-summary",
        type=Path,
        default=Path("output/benchmark_experiments/best_candidate_v4/summary.json"),
    )
    parser.add_argument(
        "--reference-run",
        type=Path,
        default=Path("data/reference_pipeline_real_run.txt"),
    )
    parser.add_argument(
        "--cghd-root",
        type=Path,
        default=Path("cghd1152"),
    )
    parser.add_argument(
        "--reclassified",
        type=Path,
        default=Path("docs/experiments/data/cghd_reclassified.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/benchmark_quality_bridge"),
    )
    args = parser.parse_args()

    report = build_report(
        candidate_summary_path=args.candidate_summary,
        reference_run_path=args.reference_run,
        cghd_root=args.cghd_root,
        reclassified_path=args.reclassified,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "quality_bridge.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, args.output_dir / "quality_bridge.md")
    print(f"Wrote quality bridge report to {args.output_dir}")


if __name__ == "__main__":
    main()
