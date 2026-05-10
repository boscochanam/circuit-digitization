from abc import ABC, abstractmethod
from typing import Any
import numpy as np

BACKENDS: dict[str, type] = {}


class PipelineBackend(ABC):
    @abstractmethod
    def run(self, image: np.ndarray, params: dict[str, Any]) -> dict[str, Any]:
        ...


def register_backend(name: str, cls: type) -> None:
    BACKENDS[name] = cls


def list_backends() -> list[str]:
    return list(BACKENDS.keys())
