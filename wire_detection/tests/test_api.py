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
    """Create a TestClient with mocked registry and cache.

    Patches both ``wire_detection.api.deps`` (used by route handlers) and
    ``wire_detection.api.server`` (used by the lifespan / startup code).
    """
    with (
        patch("wire_detection.api.deps.registry") as mock_registry,
        patch("wire_detection.api.deps.cache") as mock_cache,
        patch("wire_detection.api.server.ensure_synthetic_data"),
        patch("wire_detection.api.server.log_dataset_inventory"),
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


@patch("wire_detection.api.routes.process.PipelineFactory")
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


@patch("wire_detection.api.routes.process.PipelineFactory")
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


@patch("wire_detection.api.routes.process.PipelineFactory")
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


# ═══════════════════════════════════════════════
# /api/netlist
# ═══════════════════════════════════════════════


def test_netlist_out_of_range_returns_404(client):
    """Netlist for out-of-range index returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    resp = c.post("/api/netlist", json={"img_idx": 99, "ds": "gt_labels"})
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_netlist_no_components_returns_empty(client):
    """Netlist with no component labels returns empty nodes/components."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img
    mock_registry.load_component_labels_aligned.return_value = None

    with patch("wire_detection.api.routes.netlist._run_preset_pipeline") as mock_pipe:
        mock_pipe.return_value = {
            "lines": [], "line_count": 0, "elapsed_ms": 1.0
        }
        resp = c.post("/api/netlist", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["components"] == []
    assert isinstance(body["spice_netlist"], str)
    assert isinstance(body["warnings"], list)


def test_netlist_with_components_returns_structure(client):
    """Netlist with components returns proper structure."""
    from wire_detection.core.netlist import ComponentPin, NetNode, Netlist

    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    # Resistor component: (class_id, polygon_points, bbox)
    components = [
        (37, [(10, 10), (50, 10), (50, 30), (10, 30)], (10, 10, 50, 30)),
    ]
    mock_registry.load_component_labels_aligned.return_value = (components, Path("/fake/img.jpg"))

    # Build a real netlist
    pin = ComponentPin(
        component_idx=0, component_name="R1", pin_idx=0,
        pin_name="pin0", x=10, y=10, rel_x=0.0, rel_y=0.0,
    )
    node = NetNode(node_id=0, pins=[pin], wires=[0])
    netlist = Netlist(nodes=[node], pin_to_node={(0, "pin0"): 0})

    with (
        patch("wire_detection.api.routes.netlist._run_preset_pipeline") as mock_pipe,
        patch("wire_detection.api.routes.netlist.run_strategy") as mock_strategy,
        patch("wire_detection.api.routes.netlist.load_overrides", return_value={}),
        patch("wire_detection.api.routes.netlist.apply_overrides_to_netlist", side_effect=lambda nl, *_: nl),
        patch("wire_detection.api.routes.netlist.SpiceGenerator") as mock_gen_cls,
    ):
        mock_pipe.return_value = {
            "lines": [((10, 20), (60, 80))],
            "line_count": 1,
            "elapsed_ms": 1.0,
        }
        mock_strategy.return_value = ([pin], netlist)
        mock_gen = MagicMock()
        mock_gen.generate.return_value = ".title test\nV1 0 n1 DC 5\n"
        mock_gen._get_prefix.return_value = "R"
        mock_gen_cls.return_value = mock_gen

        resp = c.post("/api/netlist", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body
    assert "components" in body
    assert "spice_netlist" in body
    assert "warnings" in body
    assert isinstance(body["nodes"], list)
    assert isinstance(body["components"], list)
    assert ".title" in body["spice_netlist"]


def test_netlist_empty_image_list_returns_404(client):
    """Netlist when no images exist returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = []
    resp = c.post("/api/netlist", json={"img_idx": 0, "ds": "gt_labels"})
    assert resp.status_code == 404


# ═══════════════════════════════════════════════
# /api/simulate
# ═══════════════════════════════════════════════


def test_simulate_ngspice_not_available(client):
    """Simulate returns error when ngspice is not installed."""
    c, _, _ = client
    with patch("wire_detection.api.routes.netlist.SpiceSimulator") as mock_sim_cls:
        mock_sim = MagicMock()
        mock_sim.is_available.return_value = False
        mock_sim_cls.return_value = mock_sim

        resp = c.post("/api/simulate", json={
            "spice_text": ".title test\nV1 0 n1 DC 5\n"
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "ngspice" in body["error"].lower()


def test_simulate_success(client):
    """Simulate returns node voltages on success."""
    c, _, _ = client
    with patch("wire_detection.api.routes.netlist.SpiceSimulator") as mock_sim_cls:
        mock_sim = MagicMock()
        mock_sim.is_available.return_value = True
        mock_sim.run_dc_analysis.return_value = {
            "voltages": {"0": 0.0, "n1": 5.0, "n2": 2.5},
            "currents": {"v1#branch": -0.005, "v2#branch": 0.003},
        }
        mock_sim_cls.return_value = mock_sim

        resp = c.post("/api/simulate", json={
            "spice_text": ".title test\nV1 0 n1 DC 5\nR1 n1 0 1000\n"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["node_voltages"], list)
    assert isinstance(body["branch_currents"], list)
    # Should have 3 voltage nodes and 2 branch currents
    assert len(body["node_voltages"]) == 3
    assert len(body["branch_currents"]) == 2


def test_simulate_simulation_error(client):
    """Simulate returns error when simulation fails."""
    c, _, _ = client
    with patch("wire_detection.api.routes.netlist.SpiceSimulator") as mock_sim_cls:
        mock_sim = MagicMock()
        mock_sim.is_available.return_value = True
        mock_sim.run_dc_analysis.return_value = {
            "error": "convergence failed",
            "raw_output": "some output",
        }
        mock_sim_cls.return_value = mock_sim

        resp = c.post("/api/simulate", json={
            "spice_text": ".title broken\n"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "convergence" in body["error"].lower()


# ═══════════════════════════════════════════════
# /api/join_overlay
# ═══════════════════════════════════════════════


def test_join_overlay_out_of_range_returns_404(client):
    """Join overlay for out-of-range index returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    resp = c.post("/api/join_overlay", json={"img_idx": 99, "ds": "gt_labels"})
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_join_overlay_no_components_no_wires(client):
    """Join overlay with no components or wires returns warning overlay."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img
    mock_registry.load_component_labels_aligned.return_value = None

    with patch("wire_detection.api.routes.process._run_preset_pipeline_cached") as mock_pipe:
        mock_pipe.return_value = {
            "lines": [], "line_count": 0, "elapsed_ms": 1.0
        }
        resp = c.post("/api/join_overlay", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert "overlay" in body
    assert isinstance(body["overlay"], str)  # base64
    assert body["nets"] == []
    assert body["metrics"] is None
    assert len(body["warnings"]) > 0


def test_join_overlay_empty_image_list_returns_404(client):
    """Join overlay when no images exist returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = []
    resp = c.post("/api/join_overlay", json={"img_idx": 0, "ds": "gt_labels"})
    assert resp.status_code == 404


def test_join_overlay_with_wires_and_components(client):
    """Join overlay with wires and components returns overlay + nets."""
    from wire_detection.core.netlist import ComponentPin, NetNode, Netlist

    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    components = [
        (37, [(10, 10), (50, 10), (50, 30), (10, 30)], (10, 10, 50, 30)),
        (4, [(60, 60), (90, 60), (90, 80), (60, 80)], (60, 60, 90, 80)),
    ]
    mock_registry.load_component_labels_aligned.return_value = (components, Path("/fake/img.jpg"))

    pin1 = ComponentPin(0, "R1", 0, "pin0", 10, 10, 0.0, 0.0)
    pin2 = ComponentPin(1, "C1", 0, "pin0", 60, 60, 0.0, 0.0)
    node = NetNode(node_id=0, pins=[pin1, pin2], wires=[0])
    netlist = Netlist(nodes=[node], pin_to_node={(0, "pin0"): 0, (1, "pin0"): 0})

    with (
        patch("wire_detection.api.routes.process._run_preset_pipeline_cached") as mock_pipe,
        patch("wire_detection.api.routes.join_overlay.run_strategy") as mock_strategy,
        patch("wire_detection.api.routes.join_overlay.score_netlist") as mock_score,
    ):
        mock_pipe.return_value = {
            "lines": [((10, 20), (60, 80))],
            "line_count": 1,
            "elapsed_ms": 1.0,
        }
        mock_strategy.return_value = ([pin1, pin2], netlist)
        mock_score.return_value = {"total_pins": 2, "connected_pins": 2}

        resp = c.post("/api/join_overlay", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert "overlay" in body
    assert isinstance(body["overlay"], str)  # base64 PNG
    assert isinstance(body["nets"], list)
    assert len(body["nets"]) == 1
    assert body["nets"][0]["net_id"] == 0
    assert body["metrics"] is not None
    assert body["strategy"] is not None


# ═══════════════════════════════════════════════
# /api/current_overlay
# ═══════════════════════════════════════════════


def test_current_overlay_out_of_range_returns_404(client):
    """Current overlay for out-of-range index returns 404."""
    c, mock_registry, _ = client
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    resp = c.post("/api/current_overlay", json={"img_idx": 99, "ds": "gt_labels"})
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_current_overlay_no_components_no_wires(client):
    """Current overlay with no data returns warning overlay."""
    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img
    mock_registry.load_component_labels_aligned.return_value = None

    with patch("wire_detection.api.routes.process._run_preset_pipeline_cached") as mock_pipe:
        mock_pipe.return_value = {
            "lines": [], "line_count": 0, "elapsed_ms": 1.0
        }
        resp = c.post("/api/current_overlay", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert "overlay" in body
    assert isinstance(body["overlay"], str)
    assert body["available"] is False
    assert body["component_currents"] == []
    assert len(body["warnings"]) > 0


def test_current_overlay_ngspice_not_available(client):
    """Current overlay returns unavailable when ngspice not installed."""
    from wire_detection.core.netlist import ComponentPin, NetNode, Netlist

    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    components = [
        (37, [(10, 10), (50, 10), (50, 30), (10, 30)], (10, 10, 50, 30)),
    ]
    mock_registry.load_component_labels_aligned.return_value = (components, Path("/fake/img.jpg"))

    pin = ComponentPin(0, "R1", 0, "pin0", 10, 10, 0.0, 0.0)
    node = NetNode(node_id=0, pins=[pin], wires=[0])
    netlist = Netlist(nodes=[node], pin_to_node={(0, "pin0"): 0})

    with (
        patch("wire_detection.api.routes.process._run_preset_pipeline_cached") as mock_pipe,
        patch("wire_detection.api.routes.current_overlay.run_strategy") as mock_strategy,
        patch("wire_detection.api.routes.current_overlay.load_overrides", return_value={}),
        patch("wire_detection.api.routes.current_overlay.apply_overrides_to_netlist", side_effect=lambda nl, *_: nl),
        patch("wire_detection.api.routes.current_overlay.SpiceGenerator") as mock_gen_cls,
        patch("wire_detection.api.routes.current_overlay.SpiceSimulator") as mock_sim_cls,
    ):
        mock_pipe.return_value = {
            "lines": [((10, 20), (60, 80))],
            "line_count": 1,
            "elapsed_ms": 1.0,
        }
        mock_strategy.return_value = ([pin], netlist)
        mock_gen = MagicMock()
        mock_gen.generate.return_value = ".title test\nR1 n1 0 1000\n"
        mock_gen._find_gnd_node.return_value = 0
        mock_gen_cls.return_value = mock_gen
        mock_sim = MagicMock()
        mock_sim.is_available.return_value = False
        mock_sim_cls.return_value = mock_sim

        resp = c.post("/api/current_overlay", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert "ngspice" in str(body["warnings"]).lower()
    assert "spice_netlist" in body


def test_current_overlay_simulation_error(client):
    """Current overlay returns unavailable when simulation fails."""
    from wire_detection.core.netlist import ComponentPin, NetNode, Netlist

    c, mock_registry, mock_cache = client
    img = np.full((100, 100), 128, dtype=np.uint8)
    mock_registry.list_images.return_value = [Path("/fake/img.jpg")]
    mock_cache.load_image.return_value = img

    components = [
        (37, [(10, 10), (50, 10), (50, 30), (10, 30)], (10, 10, 50, 30)),
    ]
    mock_registry.load_component_labels_aligned.return_value = (components, Path("/fake/img.jpg"))

    pin = ComponentPin(0, "R1", 0, "pin0", 10, 10, 0.0, 0.0)
    node = NetNode(node_id=0, pins=[pin], wires=[0])
    netlist = Netlist(nodes=[node], pin_to_node={(0, "pin0"): 0})

    with (
        patch("wire_detection.api.routes.process._run_preset_pipeline_cached") as mock_pipe,
        patch("wire_detection.api.routes.current_overlay.run_strategy") as mock_strategy,
        patch("wire_detection.api.routes.current_overlay.load_overrides", return_value={}),
        patch("wire_detection.api.routes.current_overlay.apply_overrides_to_netlist", side_effect=lambda nl, *_: nl),
        patch("wire_detection.api.routes.current_overlay.SpiceGenerator") as mock_gen_cls,
        patch("wire_detection.api.routes.current_overlay.SpiceSimulator") as mock_sim_cls,
    ):
        mock_pipe.return_value = {
            "lines": [((10, 20), (60, 80))],
            "line_count": 1,
            "elapsed_ms": 1.0,
        }
        mock_strategy.return_value = ([pin], netlist)
        mock_gen = MagicMock()
        mock_gen.generate.return_value = ".title test\nR1 n1 0 1000\n"
        mock_gen._find_gnd_node.return_value = 0
        mock_gen_cls.return_value = mock_gen
        mock_sim = MagicMock()
        mock_sim.is_available.return_value = True
        mock_sim.run_dc_analysis.return_value = {"error": "convergence failed"}
        mock_sim_cls.return_value = mock_sim

        resp = c.post("/api/current_overlay", json={
            "img_idx": 0, "ds": "gt_labels", "preset": "best_candidate_v4"
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert "spice_netlist" in body
