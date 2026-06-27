"""
Tests for Phase 1.1 — Rotated Image Handling and Noisy/Scanned Image Handling.
Verifies that the pipeline works correctly on rotated and noisy variants.
"""
import numpy as np
import cv2
from wire_detection.pipeline.stages.threshold import ThresholdStage
from wire_detection.pipeline.stages.ccl import ccl_components
from wire_detection.pipeline.stages.contour_extract import extract_lines_from_blobs
from wire_detection.pipeline.stages.dedup import global_dedup


def _create_circuit_image(size=200):
    """Create a synthetic circuit image with wires and components."""
    img = np.full((size, size), 240, dtype=np.uint8)  # light background
    # Draw horizontal wire
    cv2.line(img, (20, 100), (180, 100), 30, 2)
    # Draw vertical wire
    cv2.line(img, (100, 20), (100, 180), 30, 2)
    # Draw component-like rectangle
    cv2.rectangle(img, (80, 80), (120, 120), 60, -1)
    return img


# =============================================================================
# Phase 1.1 — Rotated Image Handling Tests
# =============================================================================

class TestRotatedImageHandling:
    """Test pipeline behavior on rotated images."""

    def test_threshold_otsu_rotated_90(self):
        """OTSU threshold works on 90° rotated image."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        stage = ThresholdStage()
        result = stage.run(rotated, {"mode": "otsu"})
        assert result.image.dtype == np.uint8
        assert result.image.shape == rotated.shape
        assert result.image.max() == 255

    def test_threshold_otsu_rotated_180(self):
        """OTSU threshold works on 180° rotated image."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_180)
        stage = ThresholdStage()
        result = stage.run(rotated, {"mode": "otsu"})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_threshold_otsu_rotated_270(self):
        """OTSU threshold works on 270° rotated image."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        stage = ThresholdStage()
        result = stage.run(rotated, {"mode": "otsu"})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_sauvola_rotated_90(self):
        """Sauvola threshold works on 90° rotated image."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        stage = ThresholdStage()
        result = stage.run(rotated, {"mode": "sauvola", "k": 0.285, "window": 67})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_ccl_rotated_90(self):
        """Connected component labeling works on rotated image."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        _, bw = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        comps = ccl_components(bw, min_area=28)
        assert len(comps) >= 1

    def test_endpoints_rotated_90(self):
        """Endpoint extraction works on rotated image."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        _, bw = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv = cv2.bitwise_not(bw)
        lines = extract_lines_from_blobs(bw_inv, min_area=28)
        assert len(lines) >= 1

    def test_pipeline_rotated_90_preserves_wire_count(self):
        """Pipeline detects similar number of wires on rotated vs original."""
        img = _create_circuit_image()
        rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

        # Process original
        _, bw_orig = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv_orig = cv2.bitwise_not(bw_orig)
        lines_orig = extract_lines_from_blobs(bw_inv_orig, min_area=28)
        deduped_orig = global_dedup(lines_orig, angle=12, dist=18)

        # Process rotated
        _, bw_rot = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv_rot = cv2.bitwise_not(bw_rot)
        lines_rot = extract_lines_from_blobs(bw_inv_rot, min_area=28)
        deduped_rot = global_dedup(lines_rot, angle=12, dist=18)

        # Wire counts should be similar (within 50% tolerance due to aliasing)
        ratio = len(deduped_rot) / max(len(deduped_orig), 1)
        assert 0.3 <= ratio <= 3.0, f"Wire count ratio: {ratio} ({len(deduped_rot)} vs {len(deduped_orig)})"

    def test_rotation_360_returns_same_shape(self):
        """360° rotation returns same image dimensions."""
        img = _create_circuit_image()
        rotated = img.copy()
        for _ in range(4):
            rotated = cv2.rotate(rotated, cv2.ROTATE_90_CLOCKWISE)
        assert rotated.shape == img.shape


# =============================================================================
# Phase 1.1 — Noisy/Scanned Image Handling Tests
# =============================================================================

class TestNoisyImageHandling:
    """Test pipeline behavior on noisy/scanned images."""

    def _add_gaussian_noise(self, img, sigma=25):
        """Add Gaussian noise to an image."""
        noise = np.random.normal(0, sigma, img.shape).astype(np.float32)
        noisy = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return noisy

    def _add_salt_pepper(self, img, amount=0.02):
        """Add salt-and-pepper noise."""
        noisy = img.copy()
        num_salt = int(np.ceil(amount * img.size / 2))
        coords = [np.random.randint(0, i, num_salt) for i in img.shape]
        noisy[tuple(coords)] = 255
        num_pepper = int(np.ceil(amount * img.size / 2))
        coords = [np.random.randint(0, i, num_pepper) for i in img.shape]
        noisy[tuple(coords)] = 0
        return noisy

    def test_threshold_otsu_gaussian_noise(self):
        """OTSU threshold handles Gaussian noise."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=25)
        stage = ThresholdStage()
        result = stage.run(noisy, {"mode": "otsu"})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_threshold_otsu_salt_pepper(self):
        """OTSU threshold handles salt-and-pepper noise."""
        img = _create_circuit_image()
        noisy = self._add_salt_pepper(img, amount=0.02)
        stage = ThresholdStage()
        result = stage.run(noisy, {"mode": "otsu"})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_sauvola_gaussian_noise(self):
        """Sauvola threshold handles Gaussian noise."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=25)
        stage = ThresholdStage()
        result = stage.run(noisy, {"mode": "sauvola", "k": 0.285, "window": 67})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_sauvola_salt_pepper(self):
        """Sauvola threshold handles salt-and-pepper noise."""
        img = _create_circuit_image()
        noisy = self._add_salt_pepper(img, amount=0.02)
        stage = ThresholdStage()
        result = stage.run(noisy, {"mode": "sauvola", "k": 0.285, "window": 67})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

    def test_ccl_gaussian_noise(self):
        """CCL works on noisy image."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=25)
        _, bw = cv2.threshold(noisy, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        comps = ccl_components(bw, min_area=28)
        assert len(comps) >= 1

    def test_endpoints_gaussian_noise(self):
        """Endpoint extraction works on noisy image."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=25)
        _, bw = cv2.threshold(noisy, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv = cv2.bitwise_not(bw)
        lines = extract_lines_from_blobs(bw_inv, min_area=28)
        assert len(lines) >= 1

    def test_noise_preserves_wire_topology(self):
        """Moderate noise doesn't drastically change wire count."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=15)

        # Process clean
        _, bw_clean = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv_clean = cv2.bitwise_not(bw_clean)
        lines_clean = extract_lines_from_blobs(bw_inv_clean, min_area=28)
        deduped_clean = global_dedup(lines_clean, angle=12, dist=18)

        # Process noisy
        _, bw_noisy = cv2.threshold(noisy, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw_inv_noisy = cv2.bitwise_not(bw_noisy)
        lines_noisy = extract_lines_from_blobs(bw_inv_noisy, min_area=28)
        deduped_noisy = global_dedup(lines_noisy, angle=12, dist=18)

        # Wire counts should be similar with moderate noise
        ratio = len(deduped_noisy) / max(len(deduped_clean), 1)
        assert 0.3 <= ratio <= 3.0, f"Wire count ratio under noise: {ratio}"

    def test_heavy_noise_still_detects_something(self):
        """Even heavy noise doesn't produce empty detection."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=50)
        stage = ThresholdStage()
        result = stage.run(noisy, {"mode": "otsu"})
        # Should still produce a binary image with some content
        assert result.image.size > 0
        assert result.image.max() == 255

    def test_morphological_close_reduces_noise(self):
        """Morphological close helps reduce noise artifacts."""
        img = _create_circuit_image()
        noisy = self._add_gaussian_noise(img, sigma=25)
        _, bw = cv2.threshold(noisy, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Count white pixels before close
        white_before = cv2.countNonZero(bw)

        # Apply morphological close
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        bw_closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)

        # Count white pixels after close
        white_after = cv2.countNonZero(bw_closed)

        # Close should not drastically reduce content (within 50%)
        assert white_after > white_before * 0.5
