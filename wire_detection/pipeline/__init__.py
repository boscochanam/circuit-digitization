import wire_detection.pipeline.stages  # noqa: F401  triggers stage registration

from wire_detection.pipeline.types import Line, StageOutput, PipelineResult, PipelineStage
from wire_detection.pipeline.core import Pipeline
from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.pipeline.registry import list_stages, list_backends, list_joiners, register_stage

__all__ = [
    "Line",
    "StageOutput",
    "PipelineResult",
    "PipelineStage",
    "Pipeline",
    "PipelineFactory",
    "list_stages",
    "list_backends",
    "list_joiners",
    "register_stage",
]
