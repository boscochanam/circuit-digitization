import argparse
from pathlib import Path
from wire_detection.sdg.generator import SDG, SDGConfig


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic wire dataset")
    parser.add_argument("--num-images", type=int, default=1000)
    parser.add_argument("--output-dir", type=str, default="output/sdg")
    parser.add_argument("--image-size", type=int, nargs=2, default=[1024, 1024])
    parser.add_argument("--wires-per-image", type=int, nargs=2, default=[3, 15])
    parser.add_argument("--label-format", choices=["yolov8_pose", "coco", "lines"], default="yolov8_pose")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    cfg = SDGConfig(
        num_images=args.num_images,
        output_dir=Path(args.output_dir),
        image_size=tuple(args.image_size),
        wires_per_image=tuple(args.wires_per_image),
        label_format=args.label_format,
        seed=args.seed,
    )

    sdg = SDG(cfg)
    metadata = sdg.generate()
    print(f"Generated {metadata.num_images} images in {cfg.output_dir}")


if __name__ == "__main__":
    main()
