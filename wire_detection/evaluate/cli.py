import argparse
from pathlib import Path
import cv2
import json
from wire_detection.evaluate.match import evaluate
from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.config.schema import EvalConfig


def main():
    parser = argparse.ArgumentParser(description="Run evaluation on a dataset")
    parser.add_argument("--image", type=str, required=True, help="Path to image")
    parser.add_argument("--gt", type=str, required=True, help="Path to GT labels")
    parser.add_argument("--config", type=str, default=None, help="Pipeline config YAML")
    parser.add_argument("--dist-thresh", type=int, default=20, help="Distance threshold")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    image = cv2.imread(args.image, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"Error: could not read image {args.image}")
        return

    gt = []
    with open(args.gt) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                x1, y1, x2, y2 = map(int, parts[:4])
                gt.append(((x1, y1), (x2, y2)))

    import yaml
    if args.config:
        with open(args.config) as f:
            config = yaml.safe_load(f)
    else:
        config = {
            "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
            "stage_params": {
                "threshold": {"mode": "otsu"},
                "dilate": {"kernel_size": 5, "iterations": 1},
                "ccl": {"min_area": 30},
                "dedup": {"angle_thresh": 10, "dist_thresh": 12},
                "length_filter": {"min_length": 20},
            },
        }

    pipeline = PipelineFactory.from_config(config)
    result = pipeline.run(image)

    cfg = EvalConfig(dist_thresh=args.dist_thresh)
    eval_result = evaluate(result.lines, gt, dist_thresh=cfg.dist_thresh)

    output = {
        "lines": [[list(p1), list(p2)] for p1, p2 in result.lines],
        "num_lines": len(result.lines),
        "blob_count": result.blob_count,
        "elapsed_ms": result.elapsed_ms,
        "eval": {
            "tp": eval_result.tp,
            "fp": eval_result.fp,
            "fn": eval_result.fn,
            "redundant": eval_result.redundant,
            "precision": eval_result.precision,
            "recall": eval_result.recall,
            "f1": eval_result.f1,
        },
    }

    print(json.dumps(output, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)


if __name__ == "__main__":
    main()
