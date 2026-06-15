"""Tests for config validation (checklist item 6.2).

Verifies:
  1. Valid configs pass validation.
  2. Invalid configs are rejected (missing required fields, bad types, invalid Literals).
  3. Custom configs override defaults correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from wire_detection.config.schema import (
    ComponentDetectionConfig,
    DatasetConfig,
    EvalConfig,
    PipelineConfig,
    SDGConfig,
    StageConfig,
    SweepConfig,
)

# ---------------------------------------------------------------------------
# Helpers – minimal valid payloads for each model
# ---------------------------------------------------------------------------

DEFAULT_PIPELINE = {
    "stages": ["crop", "mask", "threshold", "invert", "close", "ccl", "contour_extract", "dedup"],
    "stage_params": {
        "threshold": {"params": {"mode": "sauvola", "k": 0.285, "window": 67}},
    },
}

DEFAULT_SWEEP = {
    "name": "test_sweep",
    "pipeline_params": {"threshold.k": [0.2, 0.3]},
    "base_config": {},
    "dataset": "cghd_134",
}

DEFAULT_DATASET = {
    "key": "cghd_134",
    "path": Path("data/cghd_134"),
    "image_glob": "*.png",
}


# ===== Section 1: Valid configs pass validation =====


class TestValidConfigs:
    """All of these should validate without error."""

    # --- PipelineConfig ---
    def test_pipeline_minimal(self):
        cfg = PipelineConfig(stages=["threshold", "ccl"])
        assert cfg.stages == ["threshold", "ccl"]
        assert cfg.stage_params == {}

    def test_pipeline_full(self):
        cfg = PipelineConfig(**DEFAULT_PIPELINE)
        assert len(cfg.stages) == 8

    def test_pipeline_stage_params_are_stage_config_objects(self):
        cfg = PipelineConfig(**DEFAULT_PIPELINE)
        stage_cfg = cfg.stage_params["threshold"]
        assert isinstance(stage_cfg, StageConfig)
        assert stage_cfg.params["k"] == 0.285

    # --- SweepConfig ---
    def test_sweep_minimal(self):
        cfg = SweepConfig(**DEFAULT_SWEEP)
        assert cfg.name == "test_sweep"
        assert cfg.metric == "f1"
        assert cfg.method == "grid"
        assert cfg.max_images == 200
        assert cfg.n_random == 50
        assert cfg.parallel == 4

    def test_sweep_all_metric_values(self):
        for m in ("f1", "precision", "recall"):
            cfg = SweepConfig(**{**DEFAULT_SWEEP, "metric": m})
            assert cfg.metric == m

    def test_sweep_all_method_values(self):
        for m in ("grid", "random"):
            cfg = SweepConfig(**{**DEFAULT_SWEEP, "method": m})
            assert cfg.method == m

    # --- DatasetConfig ---
    def test_dataset_minimal(self):
        cfg = DatasetConfig(**DEFAULT_DATASET)
        assert cfg.key == "cghd_134"
        assert cfg.label_format is None
        assert cfg.component_labels is False

    def test_dataset_full(self):
        data = {
            **DEFAULT_DATASET,
            "label_format": "yolov8",
            "label_glob": "*.txt",
            "component_labels": True,
            "crop_to_components": True,
            "description": "Test dataset",
        }
        cfg = DatasetConfig(**data)
        assert cfg.component_labels is True
        assert cfg.description == "Test dataset"

    def test_dataset_path_coercion(self):
        """String paths are coerced to Path objects."""
        cfg = DatasetConfig(key="x", path="/some/path", image_glob="*.png")
        assert isinstance(cfg.path, Path)
        assert str(cfg.path) == "/some/path"

    # --- SDGConfig ---
    def test_sdg_defaults(self):
        cfg = SDGConfig()
        assert cfg.num_images == 1000
        assert cfg.wires_per_image == (3, 15)
        assert cfg.wire_width == (1, 4)
        assert cfg.wire_types == ["bezier"]
        assert cfg.background_types == ["plain", "grid", "noise"]
        assert cfg.image_size == (1024, 1024)
        assert cfg.label_format == "yolov8_pose"
        assert cfg.seed is None

    def test_sdg_custom(self):
        cfg = SDGConfig(
            num_images=500,
            wire_types=["line", "arc"],
            background_types=["noise"],
            label_format="coco",
            seed=42,
        )
        assert cfg.num_images == 500
        assert cfg.wire_types == ["line", "arc"]
        assert cfg.seed == 42

    # --- EvalConfig ---
    def test_eval_defaults(self):
        cfg = EvalConfig()
        assert cfg.dist_thresh == 20
        assert cfg.dataset == ""
        assert cfg.max_images == 200

    def test_eval_custom(self):
        cfg = EvalConfig(dist_thresh=10, dataset="custom", max_images=50)
        assert cfg.dist_thresh == 10
        assert cfg.max_images == 50

    # --- ComponentDetectionConfig ---
    def test_component_detection_defaults(self):
        cfg = ComponentDetectionConfig()
        assert cfg.source == "model"
        assert cfg.confidence_threshold == 0.5

    def test_component_detection_all_sources(self):
        for src in ("model", "ground_truth", "roboflow"):
            cfg = ComponentDetectionConfig(source=src)
            assert cfg.source == src

    # --- StageConfig ---
    def test_stage_config_with_params(self):
        cfg = StageConfig(params={"k": 0.3, "window": 51})
        assert cfg.params["k"] == 0.3
        assert cfg.params["window"] == 51

    def test_stage_config_default_empty(self):
        cfg = StageConfig()
        assert cfg.params == {}


# ===== Section 2: Invalid configs are rejected =====


class TestInvalidConfigs:
    """These should all raise ValidationError."""

    # --- PipelineConfig ---
    def test_pipeline_missing_stages(self):
        with pytest.raises(ValidationError):
            PipelineConfig()

    def test_pipeline_stages_not_a_list(self):
        with pytest.raises(ValidationError):
            PipelineConfig(stages="threshold")  # type: ignore[arg-type]

    # --- SweepConfig ---
    def test_sweep_missing_name(self):
        with pytest.raises(ValidationError):
            SweepConfig(pipeline_params={}, dataset="x")  # missing 'name'

    def test_sweep_missing_pipeline_params(self):
        with pytest.raises(ValidationError):
            SweepConfig(name="x", dataset="x")  # missing 'pipeline_params'

    def test_sweep_missing_dataset(self):
        with pytest.raises(ValidationError):
            SweepConfig(name="x", pipeline_params={})  # missing 'dataset'

    def test_sweep_invalid_metric_literal(self):
        with pytest.raises(ValidationError):
            SweepConfig(**{**DEFAULT_SWEEP, "metric": "accuracy"})

    def test_sweep_invalid_method_literal(self):
        with pytest.raises(ValidationError):
            SweepConfig(**{**DEFAULT_SWEEP, "method": "bayesian"})

    def test_sweep_max_images_wrong_type(self):
        with pytest.raises(ValidationError):
            SweepConfig(**{**DEFAULT_SWEEP, "max_images": "many"})  # type: ignore[arg-type]

    def test_sweep_parallel_wrong_type(self):
        with pytest.raises(ValidationError):
            SweepConfig(**{**DEFAULT_SWEEP, "parallel": [1, 2]})  # type: ignore[arg-type]

    # --- DatasetConfig ---
    def test_dataset_missing_key(self):
        with pytest.raises(ValidationError):
            DatasetConfig(path="/tmp", image_glob="*.png")

    def test_dataset_missing_path(self):
        with pytest.raises(ValidationError):
            DatasetConfig(key="x", image_glob="*.png")

    def test_dataset_missing_image_glob(self):
        with pytest.raises(ValidationError):
            DatasetConfig(key="x", path="/tmp")

    # --- SDGConfig ---
    def test_sdg_invalid_label_format_literal(self):
        with pytest.raises(ValidationError):
            SDGConfig(label_format="coco_polygon")

    def test_sdg_invalid_wire_type_literal(self):
        with pytest.raises(ValidationError):
            SDGConfig(wire_types=["spline"])  # type: ignore[list-item]

    def test_sdg_num_images_not_int(self):
        with pytest.raises(ValidationError):
            SDGConfig(num_images=3.5)  # type: ignore[arg-type]

    # --- EvalConfig ---
    def test_eval_dist_thresh_wrong_type(self):
        with pytest.raises(ValidationError):
            EvalConfig(dist_thresh="far")  # type: ignore[arg-type]

    # --- ComponentDetectionConfig ---
    def test_component_invalid_source_literal(self):
        with pytest.raises(ValidationError):
            ComponentDetectionConfig(source="heuristic")

    def test_component_confidence_not_float(self):
        with pytest.raises(ValidationError):
            ComponentDetectionConfig(confidence_threshold="high")  # type: ignore[arg-type]


# ===== Section 3: Custom configs override defaults correctly =====


class TestConfigOverrides:
    """Verify that user-supplied values override Pydantic defaults."""

    def test_pipeline_custom_stage_params_override(self):
        cfg = PipelineConfig(
            stages=["threshold", "ccl"],
            stage_params={
                "threshold": {"params": {"mode": "otsu", "k": 0.5}},
            },
        )
        assert cfg.stage_params["threshold"].params["mode"] == "otsu"
        assert cfg.stage_params["threshold"].params["k"] == 0.5

    def test_sweep_override_all_defaults(self):
        overrides = {
            "name": "custom",
            "pipeline_params": {"a": [1, 2, 3]},
            "dataset": "custom_ds",
            "max_images": 50,
            "metric": "recall",
            "method": "random",
            "n_random": 10,
            "parallel": 8,
        }
        cfg = SweepConfig(**overrides)
        assert cfg.max_images == 50
        assert cfg.metric == "recall"
        assert cfg.method == "random"
        assert cfg.n_random == 10
        assert cfg.parallel == 8

    def test_dataset_override_defaults(self):
        cfg = DatasetConfig(
            key="new_key",
            path="/new/path",
            image_glob="*.jpg",
            label_format="yolov8",
            component_labels=True,
            crop_to_components=True,
            description="Overridden",
        )
        assert cfg.key == "new_key"
        assert cfg.label_format == "yolov8"
        assert cfg.component_labels is True
        assert cfg.description == "Overridden"

    def test_sdg_partial_override(self):
        """Override only some fields; rest should keep defaults."""
        cfg = SDGConfig(num_images=50, seed=123)
        assert cfg.num_images == 50
        assert cfg.seed == 123
        # defaults preserved
        assert cfg.wires_per_image == (3, 15)
        assert cfg.image_size == (1024, 1024)
        assert cfg.label_format == "yolov8_pose"

    def test_eval_partial_override(self):
        cfg = EvalConfig(dist_thresh=5)
        assert cfg.dist_thresh == 5
        assert cfg.dataset == ""  # default
        assert cfg.max_images == 200  # default

    def test_component_override_source(self):
        cfg = ComponentDetectionConfig(source="ground_truth")
        assert cfg.source == "ground_truth"
        assert cfg.model_path == "models/component_detection/yolo26m_obb_16class_aug.pt"
        assert cfg.confidence_threshold == 0.5

    def test_component_override_all(self):
        cfg = ComponentDetectionConfig(
            source="roboflow",
            model_path="custom/model.pt",
            confidence_threshold=0.9,
        )
        assert cfg.source == "roboflow"
        assert cfg.model_path == "custom/model.pt"
        assert cfg.confidence_threshold == 0.9

    def test_pipeline_from_raw_dict_matches_conftest_pattern(self):
        """Mirrors how conftest.py / CLI builds a pipeline config dict."""
        raw = {
            "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup"],
            "stage_params": {
                "threshold": {"params": {"mode": "otsu"}},
                "dilate": {"params": {"kernel_size": 3, "iterations": 1}},
                "ccl": {"params": {"min_area": 10}},
                "dedup": {"params": {"angle_thresh": 10, "dist_thresh": 12}},
            },
        }
        cfg = PipelineConfig(**raw)
        assert len(cfg.stages) == 6
        assert cfg.stage_params["threshold"].params["mode"] == "otsu"
        assert cfg.stage_params["ccl"].params["min_area"] == 10
