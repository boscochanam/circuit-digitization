#!/usr/bin/env python3
"""Generate PDF reports for poor and unstable detection images.

FIXED (Jun 2026): Uses exact-match Roboflow labels for occlusion on original images.
Each Roboflow image has multiple .rf.<hash> versions — some augmented, some
pixel-identical to the original. The exact-match version's labels are in the
same coordinate space as the original, so occlusion polygons are correct.
"""
import cv2, numpy as np

from wire_detection.benchmark.expanded_benchmark import preload_all_images, run_config
from wire_detection.benchmark.experiment_harness import (
    wave2_configs, build_component_mask, crop_to_roi, detect_wires_experiment,
    shift_components,
)
from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.data.dataset import find_exact_match_roboflow
from wire_detection.paths import DOCS_DIR, gt_images_dir, gt_labels_dir, hdc_root

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def load_gt_wires(gt_file, img_w, img_h):
    """Load GT wires from YOLO-OBB normalized coords."""
    wires = []
    with open(gt_file) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 9:
                coords = [float(x) for x in parts[1:9]]
                poly = np.array([[int(coords[i] * img_w), int(coords[i + 1] * img_h)]
                                 for i in range(0, 8, 2)], dtype=np.int32)
                edges = [(i, (i + 1) % 4) for i in range(4)]
                edge_lengths = [(np.linalg.norm(poly[a] - poly[b]), a, b) for a, b in edges]
                edge_lengths.sort(key=lambda x: x[0])
                m1 = (poly[edge_lengths[0][1]] + poly[edge_lengths[0][2]]) / 2
                m2 = (poly[edge_lengths[1][1]] + poly[edge_lengths[1][2]]) / 2
                wires.append(((int(m1[0]), int(m1[1])), (int(m2[0]), int(m2[1]))))
    return wires


def load_components_exact(image_name, orig_gray, w, h, gt_images, hdc_base):
    """Load component labels from the pixel-identical Roboflow version.

    CRITICAL: Uses find_exact_match_roboflow() to find the Roboflow version
    that is pixel-identical to the original image. Its labels are in the same
    coordinate space, so occlusion polygons will be correct.
    """
    orig_path = gt_images / f'{image_name}_jpg.jpg'
    result = find_exact_match_roboflow(orig_path, hdc_base=hdc_base)
    if result:
        _, label_path = result
        return ref.parse_components(label_path, w, h)
    return []


def draw_wires(img, wires, color=(0, 255, 0), thickness=1):
    vis = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for (x1, y1), (x2, y2) in wires:
        cv2.line(vis, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
    return vis


def generate_pdf(image_names, pdf_path, category_name):
    gt_labels = gt_labels_dir()
    gt_images = gt_images_dir()
    hdc_base = hdc_root()

    preload_all_images()
    cfgs = [c for c in wave2_configs() if c.name == 'best_candidate_v4']
    summary = run_config(cfgs[0])
    per_image = {r.image: r for r in summary.images}

    with PdfPages(pdf_path) as pdf:
        # Title page
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        ax.text(0.5, 0.7, 'Detection Pipeline Review', fontsize=24, fontweight='bold',
                ha='center', va='center', transform=ax.transAxes)
        ax.text(0.5, 0.5, category_name, fontsize=18, ha='center', va='center',
                transform=ax.transAxes,
                color='red' if 'poor' in str(pdf_path).lower() else 'orange')
        ax.text(0.5, 0.35, f'{len(image_names)} images', fontsize=14,
                ha='center', va='center', transform=ax.transAxes)
        ax.axis('off')
        pdf.savefig(fig, dpi=150)
        plt.close()

        for idx, image_name in enumerate(image_names):
            r = per_image.get(image_name)
            if not r:
                continue

            # Load ORIGINAL image for GT wires (correct coordinate space)
            orig_path = gt_images / f'{image_name}_jpg.jpg'
            orig_gray = cv2.imread(str(orig_path), cv2.IMREAD_GRAYSCALE)
            if orig_gray is None:
                continue
            h_orig, w_orig = orig_gray.shape

            # Load GT wires using ORIGINAL image dimensions
            gt_file = gt_labels / f'{image_name}_jpg.txt'
            gt_wires = load_gt_wires(gt_file, w_orig, h_orig) if gt_file.exists() else []

            # CRITICAL: Load components from pixel-identical Roboflow version
            # (labels in same coordinate space as original image)
            components = load_components_exact(image_name, orig_gray, w_orig, h_orig, gt_images, hdc_base)

            # Run detection pipeline on ORIGINAL image
            cfg = cfgs[0]
            occluded = build_component_mask(orig_gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)

            try:
                local_components = shift_components(components, ox, oy)
                det_wires_local = detect_wires_experiment(cropped, local_components, cfg)
                det_wires = [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                             for (x1, y1), (x2, y2) in det_wires_local]
            except Exception as e:
                print(f'  Skip {image_name}: {e}')
                det_wires = []

            # Create figure — 5 panels
            fig, axes = plt.subplots(1, 5, figsize=(18, 3.8))

            # 1: ORIGINAL image + GT wires (green) — correct coord space
            orig_bgr = cv2.cvtColor(orig_gray, cv2.COLOR_GRAY2BGR)
            gt_vis = draw_wires(orig_bgr, gt_wires, color=(0, 255, 0), thickness=2)
            axes[0].imshow(cv2.cvtColor(gt_vis, cv2.COLOR_BGR2RGB))
            axes[0].set_title('Original + GT (green)', fontsize=8)

            # 2: Occluded (on original image)
            axes[1].imshow(occluded, cmap='gray')
            axes[1].set_title('Occluded (original)', fontsize=8)

            # 3: Cropped
            axes[2].imshow(cropped, cmap='gray')
            axes[2].set_title('Cropped ROI', fontsize=8)

            # 4: Detected wires on original image (blue)
            det_bgr = cv2.cvtColor(orig_gray, cv2.COLOR_GRAY2BGR)
            det_vis = draw_wires(det_bgr, det_wires, color=(255, 0, 0), thickness=2)
            axes[3].imshow(cv2.cvtColor(det_vis, cv2.COLOR_BGR2RGB))
            axes[3].set_title('Detected (blue, original)', fontsize=8)

            # 5: Overlay — GT (green) vs Detected (red) on original
            overlay_bgr = cv2.cvtColor(orig_gray, cv2.COLOR_GRAY2BGR)
            overlay_bgr = draw_wires(overlay_bgr, gt_wires, color=(0, 255, 0), thickness=2)
            overlay_bgr = draw_wires(overlay_bgr, det_wires, color=(0, 0, 255), thickness=2)
            axes[4].imshow(cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB))
            axes[4].set_title('GT(green) vs Det(red)', fontsize=8)

            for ax in axes:
                ax.axis('off')

            fig.suptitle(f'[{idx+1}/{len(image_names)}] {image_name}  '
                         f'F1={r.f1:.3f}  TP={r.tp} FP={r.fp} FN={r.fn}',
                         fontsize=10, fontweight='bold')
            plt.tight_layout()
            pdf.savefig(fig, dpi=150, bbox_inches='tight')
            plt.close()

            if (idx + 1) % 10 == 0:
                print(f'  [{idx+1}/{len(image_names)}] done')

    print(f'Saved: {pdf_path}')


if __name__ == '__main__':
    poor = ['C101_D1_P1', 'C10_D2_P3', 'C136_D1_P1', 'C136_D2_P1', 'C136_D2_P2',
            'C167_D2_P1', 'C4_D2_P4', 'C100_D2_P4', 'C19_D1_P2', 'C8_D1_P3',
            'C9_D2_P3', 'C133_D1_P2', 'C7_D2_P2', 'C12_D2_P2', 'C187_D1_P3',
            'C115_D2_P3', 'C136_D2_P3', 'C205_D1_P2', 'C88_D2_P2', 'C111_D1_P1',
            'C28_D1_P4', 'C28_D1_P1', 'C62_D2_P2', 'C110_D1_P2', 'C105_D1_P4',
            'C92_D2_P1', 'C58_D1_P3', 'C23_D1_P2', 'C66_D2_P4', 'C8_D1_P1',
            'C182_D2_P2', 'C192_D1_P1', 'C103_D2_P4', 'C102_D1_P2']

    unstable = ['C104_D2_P2', 'C105_D2_P4', 'C104_D1_P3', 'C104_D2_P4',
                'C105_D1_P1', 'C103_D2_P1', 'C100_D1_P1', 'C104_D1_P4',
                'C245_D2_P1', 'C100_D1_P3', 'C104_D2_P3', 'C7_D2_P4', 'C127_D2_P1']

    out_dir = DOCS_DIR
    print(f'Generating poor images PDF ({len(poor)} images)...')
    generate_pdf(poor, out_dir / 'detection_poor_F1_lt_0.5.pdf', 'Poor (F1 < 0.5)')

    print(f'Generating unstable images PDF ({len(unstable)} images)...')
    generate_pdf(unstable, out_dir / 'detection_unstable_F1_0.5_0.9.pdf', 'Unstable (F1 0.5-0.9)')
