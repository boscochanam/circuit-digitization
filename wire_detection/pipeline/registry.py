from typing import Any
import numpy as np

STAGES: dict[str, type] = {}
BACKENDS: dict[str, type] = {}
JOINERS: dict[str, type] = {}


def register_stage(name: str, cls: type) -> None:
    STAGES[name] = cls


def register_backend(name: str, cls: type) -> None:
    BACKENDS[name] = cls


def register_joiner(name: str, cls: type) -> None:
    JOINERS[name] = cls


def list_stages() -> list[str]:
    return list(STAGES.keys())


def list_backends() -> list[str]:
    return list(BACKENDS.keys())


def list_joiners() -> list[str]:
    return list(JOINERS.keys())
