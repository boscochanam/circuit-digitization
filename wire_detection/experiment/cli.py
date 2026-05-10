import argparse
import json
from pathlib import Path
from wire_detection.experiment.sweep import SweepConfig, run_sweep
from wire_detection.experiment.reporter import generate_ranking_table


def main():
    parser = argparse.ArgumentParser(description="Run parameter sweep")
    parser.add_argument("--config", type=str, help="Path to sweep config YAML")
    parser.add_argument("--name", type=str, default="sweep")
    parser.add_argument("--dataset", type=str, default="hand_drawn")
    parser.add_argument("--max-images", type=int, default=200)
    parser.add_argument("--method", choices=["grid", "random"], default="grid")
    parser.add_argument("--n-random", type=int, default=50)
    parser.add_argument("--output", type=str, default="sweep_results")
    parser.add_argument("--parallel", type=int, default=4)
    args = parser.parse_args()

    if args.config:
        import yaml
        with open(args.config) as f:
            cfg_data = yaml.safe_load(f)
        cfg = SweepConfig(**cfg_data)
    else:
        cfg = SweepConfig(
            name=args.name,
            dataset=args.dataset,
            max_images=args.max_images,
            method=args.method,
            n_random=args.n_random,
            parallel=args.parallel,
        )

    result = run_sweep(cfg)
    table = generate_ranking_table(result.configs)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "ranking.md", "w") as f:
        f.write(table)

    if result.best:
        with open(output_dir / "best_config.json", "w") as f:
            json.dump({
                "params": result.best.params,
                "f1": result.best.f1,
                "precision": result.best.precision,
                "recall": result.best.recall,
            }, f, indent=2)

    print(table)
    if result.best:
        print(f"\nBest F1: {result.best.f1:.4f}")
        print(f"Best params: {result.best.params}")


if __name__ == "__main__":
    main()
