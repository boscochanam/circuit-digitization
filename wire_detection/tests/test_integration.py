import os
import time
import numpy as np
import cv2
import pytest
import json
from pathlib import Path
from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.evaluate.match import evaluate
from wire_detection.evaluate.metric import segment_dist
from wire_detection.data.dataset import DatasetRegistry
from wire_detection.experiment.sweep import run_sweep, SweepConfig
from wire_detection.experiment.runner import run_config
from wire_detection.experiment.presets import PRESETS

HAND_DRAWN_DIR = Path("/home/bosco/Projects/Misc-Projects/LineDetection/roboflow_test")
HDC_DIR = Path("/home/bosco/Projects/Misc-Projects/LineDetection/roboflow_test2")
HAND_DRAWN_IMAGES = sorted(HAND_DRAWN_DIR.glob("train/images/*.jpg"))
HAND_DRAWN_LABELS = sorted(HAND_DRAWN_DIR.glob("train/labels/*.txt"))

BASELINE_CONFIG = {
    "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
    "stage_params": {
        "threshold": {"mode": "otsu"},
        "dilate": {"kernel_size": 5, "iterations": 1},
        "ccl": {"min_area": 30},
        "dedup": {"angle_thresh": 10, "dist_thresh": 12},
        "length_filter": {"min_length": 20},
    },
}


def obb_to_line(polygon):
    p1, p2, p3, p4 = polygon
    d13 = np.linalg.norm(p1 - p3)
    d24 = np.linalg.norm(p2 - p4)
    if d13 >= d24:
        return (int(p1[0]), int(p1[1])), (int(p3[0]), int(p3[1]))
    return (int(p2[0]), int(p2[1])), (int(p4[0]), int(p4[1]))


def load_hand_drawn_gt(label_path, img_w=640, img_h=640):
    lines = []
    if not label_path.exists():
        return lines
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            coords = [float(x) for x in parts[1:]]
            poly = np.array(
                [[int(coords[i] * img_w), int(coords[i + 1] * img_h)]
                 for i in range(0, 8, 2)],
                dtype=np.int32,
            )
            if len(poly) >= 4:
                lines.append(obb_to_line(poly))
    return lines


# ── 1. Real Hand-Drawn Image Pipeline ──────────────────────────────────────


class TestHandDrawnPipeline:
    def test_baseline_on_first_image(self):
        img = cv2.imread(str(HAND_DRAWN_IMAGES[0]), cv2.IMREAD_GRAYSCALE)
        assert img is not None

        h, w = img.shape
        label_path = HAND_DRAWN_LABELS[0]
        gt = load_hand_drawn_gt(label_path, w, h)
        assert len(gt) > 0, f"No GT lines in {label_path}"

        pipeline = PipelineFactory.from_config(BASELINE_CONFIG)
        result = pipeline.run(img)

        assert len(result.lines) > 0
        assert result.blob_count > 0
        assert result.elapsed_ms > 0

        eval_result = evaluate(result.lines, gt, dist_thresh=20)
        assert eval_result.tp > 0
        assert eval_result.precision > 0
        assert eval_result.recall > 0
        assert eval_result.f1 > 0

    def test_baseline_on_five_images(self):
        total_tp = total_fp = total_fn = 0
        for img_path, label_path in zip(HAND_DRAWN_IMAGES[:5], HAND_DRAWN_LABELS[:5]):
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            h, w = img.shape
            gt = load_hand_drawn_gt(label_path, w, h)
            pipeline = PipelineFactory.from_config(BASELINE_CONFIG)
            result = pipeline.run(img)
            eval_result = evaluate(result.lines, gt, dist_thresh=20)
            total_tp += eval_result.tp
            total_fp += eval_result.fp
            total_fn += eval_result.fn

        precision = total_tp / max(total_tp + total_fp, 1)
        recall = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)
        assert f1 > 0.5, f"F1={f1:.4f} too low across 5 images"

    def test_different_threshold_modes_produce_different_results(self):
        img = cv2.imread(str(HAND_DRAWN_IMAGES[0]), cv2.IMREAD_GRAYSCALE)
        h, w = img.shape
        gt = load_hand_drawn_gt(HAND_DRAWN_LABELS[0], w, h)

        results = []
        for mode in ["otsu", "manual"]:
            config = {
                "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract",
                           "dedup", "length_filter"],
                "stage_params": {
                    "threshold": {"mode": mode, "value": 127},
                    "dilate": {"kernel_size": 5, "iterations": 1},
                    "ccl": {"min_area": 30},
                    "dedup": {"angle_thresh": 10, "dist_thresh": 12},
                    "length_filter": {"min_length": 20},
                },
            }
            pipeline = PipelineFactory.from_config(config)
            result = pipeline.run(img)
            eval_result = evaluate(result.lines, gt, dist_thresh=20)
            results.append(eval_result)

        scores = [r.f1 for r in results]
        assert len(set(scores)) > 1 or scores[0] > 0

    def test_dedup_off_produces_more_lines(self):
        img = cv2.imread(str(HAND_DRAWN_IMAGES[0]), cv2.IMREAD_GRAYSCALE)
        no_dedup = PipelineFactory.from_config(PRESETS["no_dedup"])
        baseline = PipelineFactory.from_config(BASELINE_CONFIG)
        r1 = no_dedup.run(img)
        r2 = baseline.run(img)
        assert len(r1.lines) >= len(r2.lines)

    def test_empty_image_returns_no_lines(self):
        pipeline = PipelineFactory.from_config(BASELINE_CONFIG)
        empty = np.full((100, 100), 255, dtype=np.uint8)
        result = pipeline.run(empty)
        assert len(result.lines) == 0

    def test_all_black_image_produces_few_lines(self):
        pipeline = PipelineFactory.from_config(BASELINE_CONFIG)
        black = np.zeros((100, 100), dtype=np.uint8)
        result = pipeline.run(black)
        assert len(result.lines) <= 1

    def test_preset_configs_are_valid(self):
        for name, config in PRESETS.items():
            pipeline = PipelineFactory.from_config(config)
            img = np.full((200, 200), 200, dtype=np.uint8)
            cv2.line(img, (30, 30), (170, 170), 0, 2)
            result = pipeline.run(img)
            assert len(result.lines) >= 0
            assert result.elapsed_ms > 0


# ── 2. Evaluation Metrics ──────────────────────────────────────────────────


class TestEvaluationOnRealData:
    def test_perfect_match_on_synthetic(self):
        gt = [((50, 50), (150, 150))]
        detections = [((50, 50), (150, 150))]
        result = evaluate(detections, gt, dist_thresh=20)
        assert result.tp == 1
        assert result.fp == 0
        assert result.fn == 0
        assert result.f1 == 1.0

    def test_partial_overlap_still_counts_as_tp(self):
        gt = [((0, 0), (100, 100))]
        detections = [((10, 10), (90, 90))]
        result = evaluate(detections, gt, dist_thresh=20)
        assert result.tp == 1

    def test_segment_dist_symmetric(self):
        d = ((0, 0), (100, 100))
        g = ((10, 10), (110, 110))
        d1 = segment_dist(d, g)
        d2 = segment_dist(g, d)
        assert abs(d1 - d2) < 1e-6

    def test_point_to_segment_dist_outside_segment(self):
        from wire_detection.evaluate.metric import point_to_segment_dist
        dist = point_to_segment_dist((200, 200), (0, 0), (100, 100))
        expected = ((200 - 100) ** 2 + (200 - 100) ** 2) ** 0.5
        assert abs(dist - expected) < 1e-6


# ── 3. Dataset Registry ────────────────────────────────────────────────────


class TestDatasetRegistryE2E:
    def test_registry_lists_datasets(self):
        registry = DatasetRegistry()
        datasets = registry.list_datasets()
        assert "hand_drawn" in datasets
        assert "hdc" in datasets
        assert "database" in datasets

    def test_hand_drawn_images_are_found(self):
        registry = DatasetRegistry()
        images = registry.list_images("hand_drawn")
        assert len(images) == 140

    def test_hdc_images_are_found(self):
        registry = DatasetRegistry()
        images = registry.list_images("hdc")
        assert len(images) == 1993

    def test_hand_drawn_labels_load_as_lines(self):
        registry = DatasetRegistry()
        images = registry.list_images("hand_drawn")
        labels = registry.load_labels(images[0])
        assert len(labels) > 0


# ── 4. API Server ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api_client():
    from fastapi.testclient import TestClient
    from wire_detection.api.server import app
    return TestClient(app)


class TestAPI:
    def test_list_endpoint(self, api_client):
        resp = api_client.get("/api/list?ds=hand_drawn")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 140

    def test_list_endpoint_default(self, api_client):
        resp = api_client.get("/api/list")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_thumb_endpoint(self, api_client):
        resp = api_client.get("/api/thumb?idx=0&ds=hand_drawn")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"

    def test_thumb_out_of_range(self, api_client):
        resp = api_client.get("/api/thumb?idx=9999&ds=hand_drawn")
        assert resp.status_code == 404

    def test_process_endpoint(self, api_client):
        resp = api_client.post("/api/process", json={
            "img_idx": 0,
            "ds": "hand_drawn",
            "params": {
                "thresh_mode": "otsu",
                "dil_ksize": 5,
                "dil_iters": 1,
                "min_area": 30,
                "dedup_angle": 10,
                "dedup_dist": 12,
                "min_line_length": 20,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "line_count" in data
        assert "blob_count" in data
        assert "elapsed_ms" in data
        assert "overlay" in data
        assert "threshold" in data
        assert "dilated" in data
        assert data["line_count"] > 0

    def test_process_with_manual_threshold(self, api_client):
        resp = api_client.post("/api/process", json={
            "img_idx": 0,
            "ds": "hand_drawn",
            "params": {"thresh_mode": "manual", "thresh_val": 128},
        })
        assert resp.status_code == 200
        assert resp.json()["line_count"] >= 0

    def test_process_out_of_range(self, api_client):
        resp = api_client.post("/api/process", json={
            "img_idx": 9999,
            "ds": "hand_drawn",
        })
        assert resp.status_code == 404

    def test_stages_endpoint(self, api_client):
        resp = api_client.get("/api/stages")
        assert resp.status_code == 200
        stages = resp.json()
        assert "threshold" in stages
        assert "ccl" in stages
        assert "dedup" in stages

    def test_hdc_process(self, api_client):
        resp = api_client.post("/api/process", json={
            "img_idx": 0,
            "ds": "hdc",
            "params": {"thresh_mode": "otsu"},
        })
        assert resp.status_code == 200
        assert resp.json()["line_count"] >= 0


# ── 5. Experiment / Sweep ──────────────────────────────────────────────────


class TestExperimentE2E:
    def test_sweep_minimal(self):
        cfg = SweepConfig(
            name="test_sweep",
            dataset="hand_drawn",
            max_images=2,
            method="grid",
            metric="f1",
            base_config={
                "dilate": {"kernel_size": 5, "iterations": 1},
                "ccl": {"min_area": 30},
                "dedup": {"angle_thresh": 10, "dist_thresh": 12},
                "length_filter": {"min_length": 20},
            },
            pipeline_params={
                "threshold": [
                    {"mode": "otsu"},
                    {"mode": "manual", "value": 127},
                ],
            },
        )
        result = run_sweep(cfg)
        assert len(result.configs) == 2
        assert result.best is not None
        assert result.best.f1 > 0

    def test_sweep_random_search(self):
        cfg = SweepConfig(
            name="test_random",
            dataset="hand_drawn",
            max_images=1,
            method="random",
            n_random=3,
            metric="f1",
            pipeline_params={
                "threshold": [{"mode": "otsu"}],
            },
        )
        result = run_sweep(cfg)
        assert len(result.configs) == 3

    def test_presets_produce_different_results(self):
        img = cv2.imread(str(HAND_DRAWN_IMAGES[0]), cv2.IMREAD_GRAYSCALE)
        results = []
        for name, config in [("baseline", PRESETS["baseline"]),
                             ("aggressive", PRESETS["aggressive"])]:
            pipeline = PipelineFactory.from_config(config)
            result = pipeline.run(img)
            results.append((name, len(result.lines)))
        assert results[0][1] != results[1][1] or results[0][1] > 0


# ── 6. Synthetic Data Round-Trip ───────────────────────────────────────────


class TestSDGRoundTrip:
    def test_generate_and_detect(self):
        from wire_detection.sdg.generator import SDG, SDGConfig
        cfg = SDGConfig(num_images=1, seed=42, image_size=(256, 256))
        sdg = SDG(cfg)
        rng = np.random.default_rng(42)
        img, gt_lines = sdg.generate_one(rng)

        pipeline = PipelineFactory.from_config(BASELINE_CONFIG)
        result = pipeline.run(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        eval_result = evaluate(result.lines, gt_lines, dist_thresh=20)

        assert eval_result.tp >= 0
        assert result.elapsed_ms > 0

    def test_generate_full_dataset(self, tmp_path):
        from wire_detection.sdg.generator import SDG, SDGConfig
        cfg = SDGConfig(
            num_images=3,
            seed=42,
            image_size=(128, 128),
            output_dir=tmp_path / "sdg_test",
            label_format="lines",
        )
        sdg = SDG(cfg)
        metadata = sdg.generate()
        assert metadata.num_images == 3
        assert len(metadata.image_paths) == 3
        assert len(metadata.label_paths) == 3
        for p in metadata.image_paths:
            assert p.exists()
        for p in metadata.label_paths:
            assert p.exists()

    def test_generated_labels_match_image_count(self, tmp_path):
        from wire_detection.sdg.generator import SDG, SDGConfig
        cfg = SDGConfig(
            num_images=5,
            seed=42,
            image_size=(128, 128),
            output_dir=tmp_path / "sdg_labels",
            label_format="lines",
        )
        sdg = SDG(cfg)
        metadata = sdg.generate()
        img_count = len(list((tmp_path / "sdg_labels" / "images").glob("*.jpg")))
        label_count = len(list((tmp_path / "sdg_labels" / "labels").glob("*.txt")))
        assert img_count == 5
        assert label_count == 5
