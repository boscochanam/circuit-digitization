from typing import Any, Protocol
from abc import ABC, abstractmethod
import numpy as np

Line = tuple[tuple[int, int], tuple[int, int]]


class StageOutput:
    image: np.ndarray
    data: Any

    def __init__(self, image: np.ndarray, data: Any = None):
        self.image = image
        self.data = data


class PipelineResult:
    lines: list[Line]
    raw_lines: list[Line]
    blob_count: int
    stage_outputs: dict[str, np.ndarray]
    params_used: dict[str, Any]
    elapsed_ms: float

    def __init__(
        self,
        lines: list[Line],
        raw_lines: list[Line],
        blob_count: int,
        stage_outputs: dict[str, np.ndarray],
        params_used: dict[str, Any],
        elapsed_ms: float,
    ):
        self.lines = lines
        self.raw_lines = raw_lines
        self.blob_count = blob_count
        self.stage_outputs = stage_outputs
        self.params_used = params_used
        self.elapsed_ms = elapsed_ms


class PipelineStage(ABC):
    name: str

    @abstractmethod
    def run(self, image: np.ndarray, params: dict[str, Any]) -> StageOutput:
        ...

    def visualize(self, image: np.ndarray, output: StageOutput) -> np.ndarray:
        return output.image
