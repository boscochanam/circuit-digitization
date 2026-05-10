from typing import Any
import time
import cv2
import numpy as np
from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.evaluate.match import evaluate, EvalResult


def run_config(
    image_path: str,
    config: dict[str, Any],
    ground_truth: list[tuple[tuple[int, int], tuple[int, int]]] | None = None,
) -> dict[str, Any]:
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    pipeline = PipelineFactory.from_config(config)
    start = time.perf_counter()
    result = pipeline.run(image)
    elapsed_ms = (time.perf_counter() - start) * 1000

    eval_result = None
    if ground_truth is not None:
        eval_result = evaluate(result.lines, ground_truth)

    return {
        "lines": result.lines,
        "num_lines": len(result.lines),
        "blob_count": result.blob_count,
        "elapsed_ms": elapsed_ms,
        "eval": eval_result,
    }
