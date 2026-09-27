"""Fail-closed checks for the 134-image expanded benchmark's inputs."""
from pathlib import Path

import pytest

from wire_detection.benchmark import expanded_benchmark as expanded
from wire_detection.paths import MissingDatasetError


def test_missing_cghd_images_fails_before_scoring(monkeypatch):
    monkeypatch.delenv("WIRE_GT_IMAGES", raising=False)
    monkeypatch.delenv("GT_LABELS_PATH", raising=False)
    monkeypatch.setattr(expanded, "_all_image_data", None)
    with pytest.raises(MissingDatasetError, match="WIRE_GT_IMAGES"):
        expanded.preload_all_images()


def test_missing_label_or_image_cannot_yield_partial_score(monkeypatch, tmp_path: Path):
    wires = tmp_path / "wires"
    components = tmp_path / "components"
    images = tmp_path / "images"
    for folder in (wires, components, images):
        folder.mkdir()
    monkeypatch.setattr(expanded, "GT_LABELS", wires)
    monkeypatch.setattr(expanded, "COMPONENT_LABELS", components)
    monkeypatch.setattr(expanded, "_all_image_data", None)
    monkeypatch.setenv("WIRE_GT_IMAGES", str(images))
    with pytest.raises(ValueError, match="134 matching"):
        expanded.preload_all_images()
    for index in range(134):
        name = f"C{index}_D1_P1_jpg.txt"
        (wires / name).write_text("0 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5\n")
        (components / name).write_text("1 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5\n")
    with pytest.raises(FileNotFoundError, match="CGHD image missing"):
        expanded.preload_all_images()
    (components / "C0_D1_P1_jpg.txt").unlink()
    with pytest.raises(ValueError, match="134 matching"):
        expanded.preload_all_images()
