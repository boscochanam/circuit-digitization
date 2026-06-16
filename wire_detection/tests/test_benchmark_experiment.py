from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_binary_masks,
    candidate_component_ports,
    run_experiment,
)

_has_hdc_data = Path("/home/claw/circuit-digitization/roboflow_test2").is_dir()


@pytest.mark.skipif(not _has_hdc_data, reason="HDC dataset not present")
def test_baseline_harness_matches_reference():
    summary = run_experiment(ExperimentConfig(name="baseline_control_test"))

    assert round(summary.global_f1, 4) == 0.9432
    assert summary.tp == 3461
    assert summary.fp == 133
    assert summary.fn == 63
    assert summary.red == 221


def test_alternative_threshold_methods_build_masks():
    image = np.full((64, 64), 255, dtype=np.uint8)
    image[20:44, 30:34] = 0

    for method in ("otsu", "triangle", "adaptive_mean", "adaptive_gaussian"):
        masks = build_binary_masks(
            image,
            ExperimentConfig(
                name=f"mask_{method}",
                threshold_method=method,
                fallback_ks=(),
            ),
        )
        assert masks
        assert masks[0].shape == image.shape


def test_class_aware_ports_reduce_non_connective_anchors():
    cfg = ExperimentConfig(name="port_test", class_port_gating_enabled=True)
    text_ports = candidate_component_ports(0, [(0, 0), (10, 0), (10, 8), (0, 8)], (0, 0, 10, 8), cfg)
    resistor_ports = candidate_component_ports(9, [(0, 0), (20, 0), (20, 8), (0, 8)], (0, 0, 20, 8), cfg)

    assert text_ports == []
    assert len(resistor_ports) == 2
