from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field


class StageConfig(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    stages: list[str]
    stage_params: dict[str, StageConfig] = Field(default_factory=dict)


class SweepConfig(BaseModel):
    name: str
    pipeline_params: dict[str, list[Any] | tuple[Any, Any]]
    base_config: dict[str, Any] = Field(default_factory=dict)
    dataset: str
    max_images: int = 200
    metric: Literal["f1", "precision", "recall"] = "f1"
    method: Literal["grid", "random"] = "grid"
    n_random: int = 50
    parallel: int = 4


class DatasetConfig(BaseModel):
    key: str
    path: Path
    image_glob: str
    label_format: str | None = None
    label_glob: str | None = None
    component_labels: bool = False
    crop_to_components: bool = False
    description: str = ""


class SDGConfig(BaseModel):
    num_images: int = 1000
    wires_per_image: tuple[int, int] = (3, 15)
    wire_width: tuple[int, int] = (1, 4)
    wire_types: list[Literal["bezier", "line", "arc"]] = ["bezier"]
    background_types: list[str] = ["plain", "grid", "noise"]
    image_size: tuple[int, int] = (1024, 1024)
    output_dir: Path = Path("output/sdg")
    label_format: Literal["yolov8_pose", "coco", "lines"] = "yolov8_pose"
    seed: int | None = None


class EvalConfig(BaseModel):
    dist_thresh: int = 20
    dataset: str = ""
    max_images: int = 200
