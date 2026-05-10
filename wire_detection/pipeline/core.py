import time
from typing import Any
import numpy as np
from wire_detection.pipeline.types import Line, PipelineResult
from wire_detection.pipeline.registry import STAGES


class Pipeline:
    def __init__(self, stages: list, stage_params: dict[str, dict[str, Any]] | None = None):
        self.stages = stages
        self.stage_params = stage_params or {}

    def run(self, image: np.ndarray, params: dict[str, Any] | None = None) -> PipelineResult:
        combined = dict(self.stage_params)
        if params:
            for stage_name, stage_params in params.items():
                if stage_name in combined:
                    combined[stage_name].update(stage_params)
                else:
                    combined[stage_name] = stage_params

        start = time.perf_counter()
        current = image
        stage_outputs: dict[str, np.ndarray] = {}
        raw_lines: list[Line] = []

        for stage in self.stages:
            stage_params = combined.get(stage.name, {})
            output = stage.run(current, stage_params)
            current = output.image
            stage_outputs[stage.name] = output.image

        blob_count = 0
        final_lines: list[Line] = []
        if isinstance(current, list):
            final_lines = current
        elif hasattr(current, 'dtype') and current.ndim == 2:
            from wire_detection.pipeline.stages.ccl import ccl_components
            comps = ccl_components(current, min_area=combined.get('ccl', {}).get('min_area', 30))
            blob_count = len(comps)
            from wire_detection.pipeline.stages.contour_extract import extract_lines_from_blobs
            raw_lines = extract_lines_from_blobs(current, min_area=combined.get('ccl', {}).get('min_area', 30))
            final_lines = raw_lines
            if 'dedup' in [s.name for s in self.stages]:
                from wire_detection.pipeline.stages.dedup import global_dedup
                dedup_params = combined.get('dedup', {})
                final_lines = global_dedup(
                    raw_lines,
                    angle=dedup_params.get('angle_thresh', 10),
                    dist=dedup_params.get('dist_thresh', 12),
                )
            if 'length_filter' in [s.name for s in self.stages]:
                from wire_detection.pipeline.stages.length_filter import filter_short_lines
                lf_params = combined.get('length_filter', {})
                final_lines = filter_short_lines(
                    final_lines,
                    min_length=lf_params.get('min_length', 0),
                )

        elapsed = (time.perf_counter() - start) * 1000

        return PipelineResult(
            lines=final_lines,
            raw_lines=raw_lines,
            blob_count=blob_count,
            stage_outputs=stage_outputs,
            params_used=combined,
            elapsed_ms=elapsed,
        )

    def visualize(self, image: np.ndarray, result: PipelineResult) -> np.ndarray:
        import cv2
        vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if len(image.shape) == 2 else image.copy()
        for p1, p2 in result.lines:
            cv2.line(vis, p1, p2, (0, 255, 0), 2)
        return vis
