from dataclasses import dataclass, field
from typing import Any, Literal
import itertools
import random
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.evaluate.match import evaluate
from wire_detection.data.dataset import DatasetRegistry


@dataclass
class ConfigResult:
    params: dict[str, Any]
    f1: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    redundant: int = 0


@dataclass
class SweepConfig:
    name: str = "sweep"
    pipeline_params: dict[str, list | tuple] = field(default_factory=dict)
    base_config: dict[str, Any] = field(default_factory=dict)
    dataset: str = "hand_drawn"
    max_images: int = 200
    metric: Literal["f1", "precision", "recall"] = "f1"
    method: Literal["grid", "random"] = "grid"
    n_random: int = 50
    parallel: int = 4


@dataclass
class SweepResult:
    configs: list[ConfigResult] = field(default_factory=list)
    best: ConfigResult | None = None
    ranking_table: str = ""


def _generate_param_combinations(cfg: SweepConfig) -> list[dict[str, Any]]:
    if cfg.method == "random":
        combos = []
        for _ in range(cfg.n_random):
            combo = {}
            for key, values in cfg.pipeline_params.items():
                if isinstance(values, list):
                    combo[key] = random.choice(values)
                elif isinstance(values, tuple) and len(values) == 2:
                    if isinstance(values[0], (int, float)):
                        combo[key] = random.uniform(*values)
                    else:
                        combo[key] = random.choice(values)
            combos.append(combo)
        return combos

    keys = list(cfg.pipeline_params.keys())
    value_lists = []
    for k in keys:
        v = cfg.pipeline_params[k]
        if isinstance(v, list):
            value_lists.append(v)
        elif isinstance(v, tuple):
            if all(isinstance(x, (int, float)) for x in v):
                value_lists.append(list(range(int(v[0]), int(v[1]) + 1)))
            else:
                value_lists.append(list(v))
        else:
            value_lists.append([v])

    combos = []
    for values in itertools.product(*value_lists):
        combo = dict(zip(keys, values))
        combos.append(combo)
    return combos


def _run_single(params: dict, base_config: dict, dataset_key: str, max_images: int, registry: DatasetRegistry) -> dict:
    import cv2
    import yaml

    merged = dict(base_config)
    for stage_name, stage_params in params.items():
        if stage_name in merged:
            merged[stage_name].update(stage_params)
        else:
            merged[stage_name] = stage_params

    STAGE_ORDER = ["crop", "mask", "threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"]
    active_stages = [s for s in STAGE_ORDER if s in merged]
    config = {
        "stages": active_stages,
        "stage_params": merged,
    }

    pipeline = PipelineFactory.from_config(config)
    images = registry.list_images(dataset_key)[:max_images]
    total_eval = None

    for img_path in images:
        image = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        gt_lines = registry.load_labels(img_path)
        gt = [(l.p1, l.p2) for l in gt_lines]

        result = pipeline.run(image)
        eval_result = evaluate(result.lines, gt)

        if total_eval is None:
            import copy
            total_eval = copy.deepcopy(eval_result)
        else:
            total_eval.tp += eval_result.tp
            total_eval.fp += eval_result.fp
            total_eval.redundant += eval_result.redundant
            total_eval.fn += eval_result.fn
            total_eval.gt_count += eval_result.gt_count

    if total_eval:
        return {
            "f1": total_eval.f1,
            "precision": total_eval.precision,
            "recall": total_eval.recall,
            "tp": total_eval.tp,
            "fp": total_eval.fp,
            "fn": total_eval.fn,
            "redundant": total_eval.redundant,
        }
    return {"f1": 0, "precision": 0, "recall": 0, "tp": 0, "fp": 0, "fn": 0, "redundant": 0}


def run_sweep(cfg: SweepConfig) -> SweepResult:
    registry = DatasetRegistry()
    param_combos = _generate_param_combinations(cfg)
    results = []

    for combo in param_combos:
        metrics = _run_single(combo, cfg.base_config, cfg.dataset, cfg.max_images, registry)
        config_result = ConfigResult(
            params=combo,
            f1=metrics["f1"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            tp=metrics["tp"],
            fp=metrics["fp"],
            fn=metrics["fn"],
            redundant=metrics["redundant"],
        )
        results.append(config_result)

    results.sort(key=lambda r: getattr(r, cfg.metric), reverse=True)
    best = results[0] if results else None

    return SweepResult(configs=results, best=best)
