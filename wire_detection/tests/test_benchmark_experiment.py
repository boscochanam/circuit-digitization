from __future__ import annotations

from wire_detection.benchmark.experiment_harness import ExperimentConfig, run_experiment


def test_baseline_harness_matches_reference():
    summary = run_experiment(ExperimentConfig(name="baseline_control_test"))

    assert round(summary.global_f1, 4) == 0.7066
    assert summary.tp == 248
    assert summary.fp == 70
    assert summary.fn == 52
    assert summary.red == 84
