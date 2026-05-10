from typing import Any
from wire_detection.pipeline.registry import STAGES
from wire_detection.pipeline.core import Pipeline


class PipelineFactory:
    @staticmethod
    def from_config(config: dict[str, Any]) -> Pipeline:
        stage_names = config.get("stages", [])
        stage_params = config.get("stage_params", {})

        stages = []
        for name in stage_names:
            if name not in STAGES:
                raise ValueError(f"Unknown stage: {name}. Available: {list(STAGES.keys())}")
            stages.append(STAGES[name]())

        return Pipeline(stages, stage_params)
