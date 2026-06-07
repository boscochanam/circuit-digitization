"""Pydantic models for API request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel
from typing import Any


class ProcessRequest(BaseModel):
    img_idx: int = 0
    ds: str = "gt_labels"
    params: dict[str, Any] = {}
    preset: str = "legacy_threshold"


class ProcessResponse(BaseModel):
    line_count: int
    blob_count: int
    elapsed_ms: float
    overlay: str
    threshold: str
    dilated: str | None = None
    close: str | None = None
    preset: str | None = None
    params: dict[str, Any] | None = None


class PresetInfo(BaseModel):
    label: str
    description: str
    params: dict[str, float] | None = None


class DatasetInfo(BaseModel):
    path: str | None = None
    images: int = 0
    sample: str | None = None


class NetlistRequest(BaseModel):
    img_idx: int = 0
    ds: str = "gt_labels"
    preset: str = "best_candidate_v4"
    params: dict[str, Any] = {}
    component_values: dict[str, str] | None = None  # e.g. {"0": "10k", "1": "100n"} (index-based)


class SimulateRequest(BaseModel):
    spice_text: str


class JoinOverlayRequest(BaseModel):
    img_idx: int = 0
    ds: str = "gt_labels"
    preset: str = "best_candidate_v4"
    params: dict[str, Any] = {}
    net: int | None = None          # isolate one net by id; None = all nets
    max_pin_dist: float = 30.0
    strategy: str | None = None     # join strategy name; None = production default


class SimOverlayRequest(JoinOverlayRequest):
    component_values: dict[str, str] | None = None  # e.g. {"0": "10k", "1": "100n"} (index-based)


class NetlistResponse(BaseModel):
    nodes: list[dict[str, Any]]
    components: list[dict[str, Any]]
    connections: list[dict[str, Any]]
    spice_netlist: str
    warnings: list[str] = []
