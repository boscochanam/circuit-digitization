"""Tests for wire_detection/api/server.py endpoints.

Uses FastAPI TestClient with mocked dependencies to avoid requiring
real image data on disk.
"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """Create a TestClient with mocked registry and cache."""
    with (
        patch("wire_detection.api.server.registry") as mock_registry,
        patch("wire_detection.api.server.cache") as mock_cache,
        patch("wire_detection.api.server._ensure_synthetic_data"),
        patch("wire_detection.api.server._log_dataset_inventory"),
    ):
        from wire_detection.api.server import app

        mock_registry.list_datasets.return_value = ["gt_labels", "synthetic"]
        mock_registry.get.return_value = MagicMock(
            path=tmp_path, image_glob="**/*.jpg", label_format="lines"
        )
        mock_registry.list_images.return_value = []
        mock_registry.load_component_labels.return_value = None

        with TestClient(app) as c:
            yield c, mock_registry, mock_cache


# ═══════════════════════════════════════════════
# /api/presets
# ═══════════════════════════════════════════════


def test_list_presets_returns_all_presets(client):
    """Presets endpoint returns a dict with all expected keys."""
    c, _, _ = client
    resp = c.get("/api/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "best_candidate_v4" in data
    assert "best_candidate_v2" in data
    assert "skeleton_graph_v1" in data
    assert "baseline_control" in data
    assert "legacy_threshold" in data


def test_list_presets_contains_best_candidate_v4(client):
    """best_candidate_v4 preset has expected label."""
    c, _, _ = client
    data = c.get("/api/presets").json()
    assert "Best v4" in data["best_candidate_v4"]["label"]


def test_list_presets_legacy_has_no_params(client):
    """Legacy preset entry should NOT include a params key."""
    c, _, _ = client
    data = c.get("/api/presets").json()
    legacy = data["legacy_threshold"]
    assert "params" not in legacy


def test_list_presets_non_legacy_has_params(client):
    """Non-legacy presets should include a params dict."""
    c, _, _ = client
    data = c.get("/api/presets").json()
    for key in ("best_candidate_v4", "best_candidate_v2", "skeleton_graph_v1", "baseline_control"):
        assert "params" in data[key]
        assert isinstance(data[key]["params"], dict)


# ═══════════════════════════════════════════════
# /api/list
# ═══════════════════════════════════════════════


def test_list_images_returns_array(client):
    """List endpoint returns a JSON array."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("a.jpg"), Path("b.jpg")]
    resp = c.get("/api/list")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_list_images_gt_labels_has_images(client):
    """Default dataset is gt_labels."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("img1.jpg")]
    resp = c.get("/api/list")
    mock_registry.list_images.assert_called_with("gt_labels")
    assert resp.json() == ["img1.jpg"]


def test_list_images_invalid_dataset_returns_empty(client):
    """Unknown dataset key returns empty list."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = []
    resp = c.get("/api/list?ds=nonexistent")
    assert resp.status_code == 200
    assert resp.json() == []


# ═══════════════════════════════════════════════
# /api/thumb
# ═══════════════════════════════════════════════


def test_get_thumb_returns_jpeg(client):
    """Thumbnail endpoint returns image/jpeg content type."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 200, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img
    resp = c.get("/api/thumb?idx=0")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"


def test_get_thumb_invalid_index_returns_404(client):
    """Out-of-range index returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    resp = c.get("/api/thumb?idx=5")
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_get_thumb_negative_index_returns_404(client):
    """Negative index returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    resp = c.get("/api/thumb?idx=-1")
    assert resp.status_code == 404


# ═══════════════════════════════════════════════
# /api/datasets
# ═══════════════════════════════════════════════


def test_datasets_returns_dict(client):
    """Datasets endpoint returns a dict."""
    c, _, _ = client
    resp = c.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_datasets_has_gt_labels_key(client):
    """Datasets dict includes gt_labels key."""
    c, _, _ = client
    data = c.get("/api/datasets").json()
    assert "gt_labels" in data
    assert "images" in data["gt_labels"]


def test_datasets_has_synthetic_key(client):
    """Datasets dict includes synthetic key."""
    c, _, _ = client
    data = c.get("/api/datasets").json()
    assert "synthetic" in data


# ═══════════════════════════════════════════════
# /api/process
# ═══════════════════════════════════════════════


def test_process_out_of_range_returns_404(client):
    """Processing an out-of-range index returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    resp = c.post("/api/process", json={"img_idx": 99, "ds": "gt_labels"})
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_process_preset_invalid_returns_400(client):
    """Unknown preset name returns 400 error."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img
    resp = c.post("/api/process", json={
        "img_idx": 0, "preset": "nonexistent_preset", "params": {}
    })
    assert resp.status_code == 400
    assert "Unknown preset" in resp.json()["error"]


@patch("wire_detection.api.server.PipelineFactory")
def test_process_legacy_threshold_returns_overlay(mock_factory, client):
    """Legacy preset returns overlay base64 string."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    mock_result = MagicMock()
    mock_result.lines = []
    mock_result.blob_count = 0
    mock_result.elapsed_ms = 1.0
    mock_result.stage_outputs = {"threshold": img, "close": img}
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_result
    mock_pipeline.visualize.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_factory.from_config.return_value = mock_pipeline

    resp = c.post("/api/process", json={
        "img_idx": 0, "preset": "legacy_threshold", "params": {}
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "overlay" in body
    assert isinstance(body["overlay"], str)


@patch("wire_detection.api.server.PipelineFactory")
def test_process_legacy_threshold_returns_threshold(mock_factory, client):
    """Legacy preset returns threshold image."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    mock_result = MagicMock()
    mock_result.lines = []
    mock_result.blob_count = 0
    mock_result.elapsed_ms = 1.0
    mock_result.stage_outputs = {"threshold": img, "close": img}
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_result
    mock_pipeline.visualize.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_factory.from_config.return_value = mock_pipeline

    resp = c.post("/api/process", json={
        "img_idx": 0, "preset": "legacy_threshold", "params": {}
    })
    body = resp.json()
    assert "threshold" in body


@patch("wire_detection.api.server.PipelineFactory")
def test_process_legacy_threshold_returns_line_count(mock_factory, client):
    """Legacy preset returns line_count integer."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    mock_result = MagicMock()
    mock_result.lines = [((10, 10), (50, 50))]
    mock_result.blob_count = 1
    mock_result.elapsed_ms = 2.0
    mock_result.stage_outputs = {"threshold": img, "close": img}
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_result
    mock_pipeline.visualize.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_factory.from_config.return_value = mock_pipeline

    resp = c.post("/api/process", json={
        "img_idx": 0, "preset": "legacy_threshold", "params": {}
    })
    body = resp.json()
    assert body["line_count"] == 1
    assert isinstance(body["line_count"], int)


# ═══════════════════════════════════════════════
# /api/stages
# ═══════════════════════════════════════════════


def test_stages_returns_list(client):
    """Stages endpoint returns a list."""
    c, _, _ = client
    resp = c.get("/api/stages")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ═══════════════════════════════════════════════
# Root endpoint
# ═══════════════════════════════════════════════


def test_root_returns_html(client):
    """Root endpoint returns HTML."""
    c, _, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
