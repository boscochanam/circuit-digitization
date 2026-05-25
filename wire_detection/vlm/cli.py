"""
CLI for VLM-based quality assessment of circuit schematic datasets.

Usage:
  # Classify a single image (VLM + programmatic fallback)
  wire-vlm classify image.jpg

  # Classify a directory of images
  wire-vlm classify-dir ./images/ --output results.json

  # Reclassify existing VLM results (no API calls)
  wire-vlm reclassify --vlm-results data/vlm_results.json --sweep data/sweep.json

  # Generate quality sweep scores for a directory (programmatic only)
  wire-vlm sweep ./images/ --output sweep.json

  # Generate drafter-level audit from reclassified results
  wire-vlm audit reclassified.json

  # Run the full CGHD quality audit pipeline
  wire-vlm audit-pipeline --results-dir data/
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from wire_detection.vlm.vlm_classifier import (
    OpenRouterVLM,
    ClassificationResult,
    classify_image_direct,
    classify_vlm_response,
    classify_programmatic,
    ProgrammaticScore,
    compute_quality_scores,
    reclassify_dataset,
    get_verdict,
    DEFAULT_PROMPT,
)


# ── Single image classification ───────────────────────────────────


def cmd_classify(args: argparse.Namespace) -> None:
    use_vlm = not args.no_vlm
    vlm = OpenRouterVLM() if use_vlm else None

    result = classify_image_direct(args.image, vlm=vlm, prompt=args.prompt or DEFAULT_PROMPT)

    print(json.dumps({
        "path": result.path,
        "drafter": result.drafter,
        "filename": result.filename,
        "paper_type": result.paper_type,
        "reason": result.reason,
        "grid_score": result.grid_score,
        "mean_brightness": result.mean_brightness,
        "shadow_score": result.shadow_score,
        "verdict": result.verdict,
    }, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "path": result.path,
                "paper_type": result.paper_type,
                "reason": result.reason,
                "verdict": result.verdict,
                "scores": {
                    "grid": result.grid_score,
                    "mean": result.mean_brightness,
                    "shadow": result.shadow_score,
                },
            }, f, indent=2)
        print(f"\nSaved to {args.output}")


# ── Directory classification ──────────────────────────────────────


def cmd_classify_dir(args: argparse.Namespace) -> None:
    img_dir = Path(args.dir)
    if not img_dir.is_dir():
        print(f"Error: not a directory: {args.dir}", file=sys.stderr)
        sys.exit(1)

    patterns = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    images: list[Path] = []
    for p in patterns:
        images.extend(sorted(img_dir.glob(p)))

    if not images:
        print(f"No images found in {args.dir}", file=sys.stderr)
        return

    use_vlm = args.sample_vlm and not args.no_vlm
    vlm = OpenRouterVLM() if use_vlm else None
    sample_rate = max(1, len(images) // args.sample_vlm) if args.sample_vlm and use_vlm else 0

    results: list[dict[str, Any]] = []
    for i, img_path in enumerate(images):
        use_vlm_this = use_vlm and (sample_rate == 0 or i % sample_rate == 0)
        result = classify_image_direct(
            img_path,
            vlm=vlm if use_vlm_this else None,
            prompt=args.prompt or DEFAULT_PROMPT,
        )
        results.append({
            "path": str(img_path),
            "filename": img_path.name,
            "paper_type": result.paper_type,
            "reason": result.reason,
            "grid_score": result.grid_score,
            "mean_brightness": result.mean_brightness,
            "shadow_score": result.shadow_score,
            "verdict": result.verdict,
            "vlm_used": use_vlm_this,
        })
        if (i + 1) % 20 == 0:
            print(f"  processed {i+1}/{len(images)}", file=sys.stderr)

    output = {"images": results, "total": len(results), "vlm_used": use_vlm}
    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved {len(results)} results to {args.output}")
    else:
        print(json.dumps(output, indent=2))


# ── Quality sweep (programmatic only) ──────────────────────────────


def cmd_sweep(args: argparse.Namespace) -> None:
    img_dir = Path(args.dir)
    if not img_dir.is_dir():
        print(f"Error: not a directory: {args.dir}", file=sys.stderr)
        sys.exit(1)

    import cv2
    import numpy as np

    patterns = ["*.jpg", "*.jpeg", "*.png"]
    images: list[Path] = []
    for p in patterns:
        images.extend(sorted(img_dir.glob(p)))

    if not images:
        print(f"No images found in {args.dir}", file=sys.stderr)
        return

    results: list[dict[str, Any]] = []
    for img_path in images:
        gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        scores = compute_quality_scores(gray)
        results.append({
            "path": str(img_path),
            "filename": img_path.name,
            "mean": round(scores.mean, 1),
            "contrast": round(scores.contrast, 2),
            "grid_score": round(scores.grid_score, 1),
            "shadow_score": round(scores.shadow_score, 1),
            "composite": round(scores.composite, 4),
            "stratum": scores.stratum,
        })

    output = {"images": results, "total": len(results)}
    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Saved {len(results)} sweep results to {args.output}")
    else:
        print(json.dumps(output, indent=2))


# ── Reclassify existing VLM results ──────────────────────────────


def cmd_reclassify(args: argparse.Namespace) -> None:
    def load_json(path: str) -> Any:
        with open(path) as f:
            text = f.read()
        text = re.sub(r",\s*\]", "]", text)
        text = re.sub(r",\s*\}", "}", text)
        return json.loads(text)

    vlm_results = load_json(args.vlm_results)
    sweep = load_json(args.sweep)
    results = reclassify_dataset(vlm_results, sweep, use_vlm_fallback=True)

    output = [
        {
            "path": r.path,
            "drafter": r.drafter,
            "filename": r.filename,
            "paper_type": r.paper_type,
            "reason": r.reason,
            "grid_score": r.grid_score,
            "mean_brightness": r.mean_brightness,
            "shadow_score": r.shadow_score,
            "verdict": r.verdict,
        }
        for r in results
    ]

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Saved {len(output)} reclassified results to {args.output}")
    else:
        print(json.dumps(output, indent=2))


# ── Drafter-level audit ──────────────────────────────────────────


def cmd_audit(args: argparse.Namespace) -> None:
    with open(args.input) as f:
        reclassified = json.load(f)

    drafters: dict[str, Any] = {}
    for r in reclassified:
        d = r.get("drafter", "unknown")
        if d not in drafters:
            drafters[d] = {"samples": [], "GOOD": 0, "MARGINAL": 0, "REJECT": 0, "NODATA": 0, "types": Counter(), "total": 0}
        drafters[d]["samples"].append(r)
        drafters[d][r["verdict"]] += 1
        drafters[d]["total"] += 1
        drafters[d]["types"][r["paper_type"]] += 1

    for d in drafters:
        drafters[d]["samples"].sort(key=lambda x: x["grid_score"])

    drafter_verdicts: dict[str, Any] = {}
    for d, info in drafters.items():
        total = info["total"]
        good_pct = info["GOOD"] / total * 100
        marginal_pct = info["MARGINAL"] / total * 100
        reject_pct = info["REJECT"] / total * 100
        nodata_pct = info["NODATA"] / total * 100

        if nodata_pct >= 50:
            verdict = "NODATA"
        elif good_pct + marginal_pct >= 50:
            verdict = "KEEP"
        elif reject_pct >= 50:
            verdict = "REJECT"
        else:
            verdict = "MIXED"

        drafter_verdicts[d] = {
            "verdict": verdict,
            "good_pct": round(good_pct, 0),
            "marginal_pct": round(marginal_pct, 0),
            "reject_pct": round(reject_pct, 0),
            "nodata_pct": round(nodata_pct, 0),
            "counts": {"GOOD": info["GOOD"], "MARGINAL": info["MARGINAL"], "REJECT": info["REJECT"], "NODATA": info["NODATA"]},
            "top_types": dict(info["types"].most_common(3)),
            "primary_issue": info["types"].most_common(1)[0][0] if info["types"] else "unknown",
        }

    audit = {
        "total_images_sampled": len(reclassified),
        "total_drafters": len(drafters),
        "drafters": drafter_verdicts,
        "recommended_keep": sorted([d for d, v in drafter_verdicts.items() if v["verdict"] == "KEEP"],
                                    key=lambda x: int(x.split("_")[1].lstrip("-"))),
        "recommended_reject": sorted([d for d, v in drafter_verdicts.items() if v["verdict"] == "REJECT"],
                                      key=lambda x: int(x.split("_")[1].lstrip("-"))),
        "recommended_mixed": sorted([d for d, v in drafter_verdicts.items() if v["verdict"] == "MIXED"],
                                     key=lambda x: int(x.split("_")[1].lstrip("-"))),
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(audit, f, indent=2, default=str)
        print(f"Saved audit to {args.output}")
    else:
        print(json.dumps(audit, indent=2, default=str))

    # Print summary
    print(f"\n=== Drafter Audit ===")
    print(f"Sampled: {audit['total_images_sampled']} images ({audit['total_drafters']} drafters)")
    for v in ["KEEP", "MIXED", "REJECT"]:
        drafters_in = audit[f"recommended_{v.lower()}"]
        if drafters_in:
            print(f"  {v}: {', '.join(drafters_in)}")


# ── Full audit pipeline ──────────────────────────────────────────


def cmd_audit_pipeline(args: argparse.Namespace) -> None:
    """Run full reclassify + audit from workspace data directory."""
    data_dir = Path(args.results_dir)
    if not data_dir.is_dir():
        print(f"Error: not a directory: {args.results_dir}", file=sys.stderr)
        sys.exit(1)

    vlm_file = data_dir / "cghd_vlm_results.json"
    retry_file = data_dir / "cghd_vlm_retry.json"
    sweep_file = data_dir / "cghd_quality_sweep.json"

    if not vlm_file.exists():
        print(f"Error: {vlm_file} not found", file=sys.stderr)
        sys.exit(1)

    def load_json(path: Path) -> Any:
        with open(path) as f:
            text = f.read()
        text = re.sub(r",\s*\]", "]", text)
        text = re.sub(r",\s*\}", "}", text)
        return json.loads(text)

    # Merge retry results into primary
    vlm_results = load_json(vlm_file)
    if retry_file.exists():
        retry = load_json(retry_file)
        path_map = {e["path"]: e for e in vlm_results}
        for entry in retry:
            old = path_map.get(entry["path"], {}).get("vlm_response", "").strip()
            new = (entry.get("vlm_response") or "").strip()
            if new and len(new) > 10 and old in ("The", "So", ""):
                path_map[entry["path"]] = entry
        vlm_results = list(path_map.values())

    sweep = load_json(sweep_file) if sweep_file.exists() else []
    results = reclassify_dataset(vlm_results, sweep, use_vlm_fallback=True)

    output = [
        {
            "path": r.path,
            "drafter": r.drafter,
            "filename": r.filename,
            "paper_type": r.paper_type,
            "reason": r.reason,
            "grid_score": r.grid_score,
            "mean_brightness": r.mean_brightness,
            "shadow_score": r.shadow_score,
            "verdict": r.verdict,
        }
        for r in results
    ]

    reclassified_path = data_dir / "cghd_reclassified.json"
    with open(reclassified_path, "w") as f:
        json.dump(output, f, indent=2)

    # Now run audit using the reclassified output
    class AuditArgs:
        input = str(reclassified_path)
        output = str(data_dir / "cghd_final_audit.json") if args.output_audit else None

    audit_args = AuditArgs()
    # Read and audit
    with open(audit_args.input) as f:
        reclassified_data = json.load(f)

    drafters: dict[str, Any] = {}
    for r in reclassified_data:
        d = r.get("drafter", "unknown")
        if d not in drafters:
            drafters[d] = {"GOOD": 0, "MARGINAL": 0, "REJECT": 0, "NODATA": 0, "types": Counter(), "total": 0}
        drafters[d][r["verdict"]] += 1
        drafters[d]["total"] += 1
        drafters[d]["types"][r["paper_type"]] += 1

    drafter_verdicts = {}
    for d, info in drafters.items():
        total = info["total"]
        good_pct = info["GOOD"] / total * 100
        marginal_pct = info["MARGINAL"] / total * 100
        reject_pct = info["REJECT"] / total * 100
        nodata_pct = info["NODATA"] / total * 100

        if nodata_pct >= 50:
            verdict = "NODATA"
        elif good_pct + marginal_pct >= 50:
            verdict = "KEEP"
        elif reject_pct >= 50:
            verdict = "REJECT"
        else:
            verdict = "MIXED"

        drafter_verdicts[d] = {
            "verdict": verdict,
            "good_pct": round(good_pct, 0),
            "marginal_pct": round(marginal_pct, 0),
            "reject_pct": round(reject_pct, 0),
            "nodata_pct": round(nodata_pct, 0),
            "counts": {"GOOD": info["GOOD"], "MARGINAL": info["MARGINAL"], "REJECT": info["REJECT"], "NODATA": info["NODATA"]},
            "top_types": dict(info["types"].most_common(3)),
            "primary_issue": info["types"].most_common(1)[0][0] if info["types"] else "unknown",
        }

    audit = {
        "total_images_sampled": len(reclassified_data),
        "total_drafters": len(drafters),
        "drafters": drafter_verdicts,
        "recommended_keep": sorted([d for d, v in drafter_verdicts.items() if v["verdict"] == "KEEP"],
                                    key=lambda x: int(x.split("_")[1].lstrip("-"))),
        "recommended_reject": sorted([d for d, v in drafter_verdicts.items() if v["verdict"] == "REJECT"],
                                      key=lambda x: int(x.split("_")[1].lstrip("-"))),
        "recommended_mixed": sorted([d for d, v in drafter_verdicts.items() if v["verdict"] == "MIXED"],
                                     key=lambda x: int(x.split("_")[1].lstrip("-"))),
    }

    if audit_args.output:
        with open(audit_args.output, "w") as f:
            json.dump(audit, f, indent=2, default=str)

    # Print summary
    print(f"\n=== Audit Pipeline Complete ===")
    print(f"Reclassified: {len(output)} images → {reclassified_path}")
    if audit_args.output:
        print(f"Audit: {audit_args.output}")
    print(f"Recommended KEEP: {', '.join(audit.get('recommended_keep', []))}")


# ── Main CLI parser ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VLM-based quality assessment for circuit schematic datasets"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # classify
    p_classify = sub.add_parser("classify", help="Classify a single image")
    p_classify.add_argument("image", type=str, help="Path to image")
    p_classify.add_argument("--no-vlm", action="store_true", help="Skip VLM call, use programmatic only")
    p_classify.add_argument("--prompt", type=str, default=None, help="Custom VLM prompt")
    p_classify.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")

    # classify-dir
    p_dir = sub.add_parser("classify-dir", help="Classify all images in a directory")
    p_dir.add_argument("dir", type=str, help="Directory with images")
    p_dir.add_argument("--no-vlm", action="store_true", help="Skip VLM, programmatic only")
    p_dir.add_argument("--prompt", type=str, default=None, help="Custom VLM prompt")
    p_dir.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")
    p_dir.add_argument("--sample-vlm", type=int, default=10,
                        help="Use VLM on every Nth image when processing a directory (default: 10)")

    # sweep
    p_sweep = sub.add_parser("sweep", help="Compute programmatic quality scores for images in a directory")
    p_sweep.add_argument("dir", type=str, help="Directory with images")
    p_sweep.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")

    # reclassify
    p_reclass = sub.add_parser("reclassify", help="Reclassify existing VLM results (no API calls)")
    p_reclass.add_argument("--vlm-results", type=str, required=True, help="VLM results JSON")
    p_reclass.add_argument("--sweep", type=str, required=True, help="Quality sweep JSON")
    p_reclass.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")

    # audit
    p_audit = sub.add_parser("audit", help="Generate drafter-level audit from reclassified results")
    p_audit.add_argument("input", type=str, help="Reclassified JSON")
    p_audit.add_argument("--output", "-o", type=str, default=None, help="Output JSON path")

    # audit-pipeline
    p_pipe = sub.add_parser("audit-pipeline", help="Run full reclassify + audit from data directory")
    p_pipe.add_argument("--results-dir", type=str, default="docs/experiments/data",
                         help="Directory with VLM/sweep JSONs")
    p_pipe.add_argument("--output-audit", action="store_true", help="Save audit JSON")

    args = parser.parse_args()

    dispatch = {
        "classify": cmd_classify,
        "classify-dir": cmd_classify_dir,
        "sweep": cmd_sweep,
        "reclassify": cmd_reclassify,
        "audit": cmd_audit,
        "audit-pipeline": cmd_audit_pipeline,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
