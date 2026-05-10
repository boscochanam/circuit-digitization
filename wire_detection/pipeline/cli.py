import argparse
import json
import cv2
from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.pipeline.registry import list_stages


def main():
    parser = argparse.ArgumentParser(description="Run pipeline on a single image")
    parser.add_argument("image", type=str, help="Path to input image")
    parser.add_argument("--config", type=str, default=None, help="Pipeline config JSON or YAML")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--list-stages", action="store_true", help="List available stages")
    args = parser.parse_args()

    if args.list_stages:
        print("Available stages:", ", ".join(list_stages()))
        return

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

    image = cv2.imread(args.image, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"Error: could not read image {args.image}")
        return

    pipeline = PipelineFactory.from_config(config)
    result = pipeline.run(image)

    output = {
        "lines": [[list(p1), list(p2)] for p1, p2 in result.lines],
        "num_lines": len(result.lines),
        "blob_count": result.blob_count,
        "elapsed_ms": result.elapsed_ms,
        "params_used": result.params_used,
    }

    print(json.dumps(output, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)


if __name__ == "__main__":
    main()
