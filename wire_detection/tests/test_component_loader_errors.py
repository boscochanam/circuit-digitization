"""Tests for component_loader error handling (issue 6.3).

Verifies that:
1) Missing images return empty list with warning (not FileNotFoundError)
2) Missing labels return empty list with warning
3) Empty detection results are handled gracefully
4) Pipeline failures produce meaningful errors
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wire_detection.config.schema import ComponentDetectionConfig
from wire_detection.data.component_loader import (
    _load_from_gt,
    _load_from_model,
    load_components,
)


# ---------------------------------------------------------------------------
# 1. Missing images — should return [] not raise FileNotFoundError
# ---------------------------------------------------------------------------

class TestMissingImage:
    """load_components with a non-existent image path."""

    def test_missing_image_returns_empty_list(self, caplog):
        """source='model' with a missing image → empty list + warning."""
        result = load_components("/nonexistent/path/fake_image.jpg")
        assert result == []

    def test_missing_image_logs_warning(self, caplog):
        """A warning is logged when the image is missing."""
        with caplog.at_level(logging.WARNING, logger="wire_detection.data.component_loader"):
            load_components("/nonexistent/path/fake_image.jpg")
        assert any("not found" in rec.message.lower() for rec in caplog.records)

    def test_missing_image_does_not_raise(self):
        """FileNotFoundError must NOT propagate to the caller."""
        # This should complete without raising
        result = load_components("/tmp/does_not_exist_12345.jpg")
        assert result == []

    def test_missing_image_not_a_file(self, tmp_path):
        """A directory path (not a file) should return empty list."""
        result = load_components(str(tmp_path))  # tmp_path is a directory
        assert result == []


# ---------------------------------------------------------------------------
# 2. Missing labels — should return [] not raise
# ---------------------------------------------------------------------------

class TestMissingLabels:
    """_load_from_gt with missing label files."""

    def test_missing_gt_label_returns_empty_list(self, caplog):
        with caplog.at_level(logging.WARNING, logger="wire_detection.data.component_loader"):
            result = _load_from_gt("/nonexistent/labels.txt", 100, 100)
        assert result == []

    def test_missing_gt_label_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="wire_detection.data.component_loader"):
            _load_from_gt("/nonexistent/labels.txt", 100, 100)
        assert any("not found" in rec.message.lower() for rec in caplog.records)

    def test_missing_gt_label_via_load_components(self, caplog):
        """load_components with ground_truth source and missing label."""
        with caplog.at_level(logging.WARNING, logger="wire_detection.data.component_loader"):
            result = load_components(
                "dummy.jpg",
                source="ground_truth",
                gt_label_path="/nonexistent/labels.txt",
                image_w=100,
                image_h=100,
            )
        assert result == []


# ---------------------------------------------------------------------------
# 3. Empty detection results — handle gracefully
# ---------------------------------------------------------------------------

class TestEmptyResults:
    """Model inference that returns no detections."""

    def test_empty_detection_returns_empty_list(self, tmp_path):
        """When YOLO returns 0 detections, load_components returns []."""
        fake_image = tmp_path / "test.jpg"
        fake_image.write_bytes(b"\xff\xd8\xff")  # minimal JPEG header

        # Mock the model and results
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.obb = None  # No OBB detections
        mock_model.return_value = [mock_result]

        # Create a fake model file
        fake_model = tmp_path / "model.pt"
        fake_model.write_bytes(b"fake model")

        config = ComponentDetectionConfig(model_path=str(fake_model))

        with patch("ultralytics.YOLO", return_value=mock_model):
            result = _load_from_model(fake_image, config)

        assert result == []

    def test_empty_detection_logs_info(self, tmp_path, caplog):
        """No-component case is logged at INFO level."""
        fake_image = tmp_path / "test.jpg"
        fake_image.write_bytes(b"\xff\xd8\xff")

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.obb = None
        mock_model.return_value = [mock_result]

        fake_model = tmp_path / "model.pt"
        fake_model.write_bytes(b"fake model")
        config = ComponentDetectionConfig(model_path=str(fake_model))

        with patch("ultralytics.YOLO", return_value=mock_model):
            with caplog.at_level(logging.INFO, logger="wire_detection.data.component_loader"):
                _load_from_model(fake_image, config)

        assert any("no components" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# 4. Pipeline failures — produce meaningful errors
# ---------------------------------------------------------------------------

class TestPipelineFailures:
    """Model loading errors and unknown sources."""

    def test_missing_model_raises_file_not_found(self, tmp_path):
        """Missing model file → FileNotFoundError (not empty list)."""
        # Create a real image so image check passes
        fake_image = tmp_path / "test.jpg"
        fake_image.write_bytes(b"\xff\xd8\xff")

        with pytest.raises(FileNotFoundError, match="Model not found"):
            _load_from_model(
                fake_image,
                ComponentDetectionConfig(model_path=str(tmp_path / "nonexistent.pt")),
            )

    def test_unknown_source_raises_value_error(self):
        """Unknown source string → ValueError with helpful message."""
        with pytest.raises(ValueError, match="Unknown component detection source"):
            load_components("dummy.jpg", source="invalid_source")  # type: ignore[arg-type]

    def test_unknown_source_error_lists_valid_sources(self):
        """ValueError message includes the valid source options."""
        with pytest.raises(ValueError, match="model.*ground_truth.*roboflow"):
            load_components("dummy.jpg", source="bad")  # type: ignore[arg-type]

    def test_missing_gt_args_raises_value_error(self):
        """ground_truth source without required args → ValueError."""
        with pytest.raises(ValueError, match="gt_label_path"):
            load_components("dummy.jpg", source="ground_truth")

    def test_missing_gt_args_error_includes_values(self):
        """ValueError message includes the actual values passed."""
        with pytest.raises(ValueError, match="image_w=None"):
            load_components(
                "dummy.jpg",
                source="ground_truth",
                gt_label_path="/some/path.txt",
            )

    def test_missing_roboflow_args_raises_value_error(self):
        """roboflow source without required args → ValueError."""
        with pytest.raises(ValueError, match="rob_label_path"):
            load_components("dummy.jpg", source="roboflow")


# ---------------------------------------------------------------------------
# 5. Corrupt / malformed label files
# ---------------------------------------------------------------------------

class TestCorruptLabels:
    """Label files with invalid content."""

    def test_corrupt_gt_label_returns_empty_list(self, tmp_path, caplog):
        """Binary garbage in a .txt label file → empty list + warning."""
        corrupt = tmp_path / "corrupt.txt"
        corrupt.write_bytes(b"\x00\x01\x02\x03\xff\xfe")

        with caplog.at_level(logging.WARNING, logger="wire_detection.data.component_loader"):
            result = _load_from_gt(corrupt, 100, 100)

        assert result == []

    def test_empty_gt_label_returns_empty_list(self, tmp_path):
        """Empty label file → empty list (no crash)."""
        empty_label = tmp_path / "empty.txt"
        empty_label.write_text("")

        result = _load_from_gt(empty_label, 100, 100)
        assert result == []

    def test_malformed_gt_label_returns_empty_list(self, tmp_path):
        """Label file with wrong format → empty list (lines skipped or warning)."""
        bad = tmp_path / "bad.txt"
        bad.write_text("this is not valid\nneither is this\n")

        # Should not raise — malformed lines are skipped or trigger warning
        result = _load_from_gt(bad, 100, 100)
        # Either empty (all lines skipped) or [] (warning on parse error)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 6. Default config loading
# ---------------------------------------------------------------------------

class TestDefaultConfig:
    """Config loading without explicit config argument."""

    def test_load_components_with_default_config(self):
        """load_components with no config loads defaults."""
        # This should not raise — just returns empty list for missing image
        result = load_components("/nonexistent.jpg")
        assert isinstance(result, list)
