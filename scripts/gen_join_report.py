#!/usr/bin/env python3
"""Generate PDF report: graph_rescue vs degree_budget_completion on 134 real images.
FIXED: uses Roboflow augmented images to match labels (alignment fix)."""
from __future__ import annotations
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from wire_detection.api.routes.netlist import _run_preset_pipeline
from wire_detection.core.join_strategies import make_pins, run_strategy, score_netlist
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.synthgt.candidate_joins import degree_budget_completion
from wire_detection.paths import DOCS_DIR, gt_images_dir, gt_labels_dir, hdc_root

HDC_SPLITS = ["train", "valid", "test"]
from wire_detection.benchmark import reference_pipeline as ref

TMP_DIR = DOCS_DIR / "_report_imgs"
TMP_DIR.mkdir(parents=True, exist_ok=True)

_FILTER_OUT = {44, 51}
_OVERLAP_PRIORITY = {49: 31, 9: 31, 16: 31, 14: 46, 42: 36}


def iou(b1, b2):
    x1 = max(b1[0], b2[0]); y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2]); y2 = min(b1[3], b2[3])
    inter = max(0, x2-x1) * max(0, y2-y1)
    a1 = (b1[2]-b1[0]) * (b1[3]-b1[1])
    a2 = (b2[2]-b2[0]) * (b2[3]-b2[1])
    return inter / max(1, a1 + a2 - inter)


def clean_components(raw):
    comps = [c for c in raw if c[0] not in _FILTER_OUT]
    comps = sorted(comps, key=lambda c: -(c[2][2]-c[2][0])*(c[2][3]-c[2][1]))
    keep = []
    for c in comps:
        cls_id, poly, bbox = c
        dominated = False
        for k_cls, k_poly, k_bbox in keep:
            if iou(bbox, k_bbox) > 0.3:
                if cls_id in _OVERLAP_PRIORITY and _OVERLAP_PRIORITY[cls_id] == k_cls:
                    dominated = True
                    break
                if k_cls in _OVERLAP_PRIORITY and _OVERLAP_PRIORITY[k_cls] == cls_id:
                    keep = [(kc, kp, kb) for kc, kp, kb in keep if (kc, kp, kb) != (k_cls, k_poly, k_bbox)]
                    break
        if not dominated:
            keep.append(c)
    return keep


def find_hdc_label(hdc_base: Path, image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = hdc_base / split / "labels"
        for pat in [f"{image_name}_jpg.rf.*.txt"]:
            matches = sorted(label_dir.glob(pat))
            if matches:
                return matches[0]
    return None


def find_rob_image(hdc_base: Path, image_name: str) -> Path | None:
    """Find the Roboflow augmented image (matches the label orientation)."""
    for split in HDC_SPLITS:
        img_dir = hdc_base / split / "images"
        matches = sorted(img_dir.glob(f"{image_name}_jpg.rf.*.jpg"))
        if matches:
            return matches[0]
    return None


def score_join(name, wires, components, pins):
    if name == "degree_budget_completion":
        netlist = degree_budget_completion(wires, components, pins)
    else:
        _, netlist = run_strategy(name, wires, components, std_pins=pins)
    return score_netlist(wires, components, pins, netlist), netlist


def draw_netlist_on_image(gray, wires, components, netlist, pins):
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    palette = [
        (0, 200, 0), (0, 100, 255), (255, 100, 0), (200, 0, 200),
        (0, 200, 200), (200, 200, 0), (255, 50, 50), (100, 100, 255),
        (0, 150, 100), (180, 0, 100), (100, 180, 0), (50, 50, 200),
    ]
    node_colors = {}
    for i, node in enumerate(netlist.nodes):
        if len(node.pins) >= 2:
            node_colors[node.node_id] = palette[i % len(palette)]

    for comp in components:
        bbox = comp[2]
        cv2.rectangle(img, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])),
                      (100, 100, 100), 1)

    pin_node = dict(netlist.pin_to_node)
    for ep1, ep2 in wires:
        color = (180, 180, 180)
        for ep in [ep1, ep2]:
            best_node = None
            best_dist = 30
            for p in pins:
                d = ((ep[0] - p.x)**2 + (ep[1] - p.y)**2)**0.5
                if d < best_dist:
                    best_dist = d
                    best_node = pin_node.get((p.component_idx, p.pin_name))
            if best_node is not None and best_node in node_colors:
                color = node_colors[best_node]
                break
        cv2.line(img, (int(ep1[0]), int(ep1[1])), (int(ep2[0]), int(ep2[1])), color, 2)

    for p in pins:
        cv2.circle(img, (int(p.x), int(p.y)), 3, (0, 255, 255), -1)
    return img


def make_3panel(image_name, gray, wires, components, pins, gr_nl, dbc_nl):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)

    p1 = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    for comp in components:
        bbox = comp[2]
        cv2.rectangle(p1, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])),
                      (100, 100, 100), 1)
    for ep1, ep2 in wires:
        cv2.line(p1, (int(ep1[0]), int(ep1[1])), (int(ep2[0]), int(ep2[1])), (0, 200, 0), 2)
    for p in pins:
        cv2.circle(p1, (int(p.x), int(p.y)), 3, (0, 255, 255), -1)

    p2 = draw_netlist_on_image(gray, wires, components, gr_nl, pins)
    p3 = draw_netlist_on_image(gray, wires, components, dbc_nl, pins)

    for panel, label in [(p1, "Detected"), (p2, "graph_rescue"), (p3, "degree_budget")]:
        pil = Image.fromarray(cv2.cvtColor(panel, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        draw.rectangle([0, 0, len(label)*9 + 16, 22], fill=(0, 0, 0))
        draw.text((8, 3), label, fill=(255, 255, 255), font=font)
        panel[:] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    return np.hstack([p1, p2, p3])


def run_benchmark():
    gt_labels = gt_labels_dir()
    gt_images = gt_images_dir()
    hdc_base = hdc_root()

    all_images = sorted(gt_labels.glob("*_jpg.txt"))
    results = []
    t0 = time.time()
    aug_stats = {"identical": 0, "augmented": 0, "no_rob_image": 0}

    for i, gt_file in enumerate(all_images):
        image_name = gt_file.stem.replace("_jpg", "")

        # Load Roboflow augmented image (matches label orientation)
        rob_img_path = find_rob_image(hdc_base, image_name)
        if rob_img_path is None:
            # Fallback to original GT image
            rob_img_path = gt_images / f"{image_name}_jpg.jpg"
            aug_stats["no_rob_image"] += 1

        gray = cv2.imread(str(rob_img_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue

        # Check if augmented or identical
        orig = cv2.imread(str(gt_images / f"{image_name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        if orig is not None and np.array_equal(orig, gray):
            aug_stats["identical"] += 1
        else:
            aug_stats["augmented"] += 1

        h, w = gray.shape
        hdc_path = find_hdc_label(hdc_base, image_name)
        raw_components = ref.parse_components(hdc_path, w, h) if hdc_path else []
        components = clean_components(raw_components)

        pipeline_result = _run_preset_pipeline(gray, "best_candidate_v4", {}, image_path=str(rob_img_path))
        wires = pipeline_result.get("lines", [])

        if not components or not wires:
            continue

        pins = make_pins(wires, components)
        if not pins:
            continue

        gr_score, gr_nl = score_join("graph_rescue", wires, components, pins)
        dbc_score, dbc_nl = score_join("degree_budget_completion", wires, components, pins)
        results.append({
            "image": image_name, "gr": gr_score, "dbc": dbc_score,
            "gray": gray, "wires": wires, "components": components,
            "raw_count": len(raw_components), "clean_count": len(components),
            "pins": pins, "gr_nl": gr_nl, "dbc_nl": dbc_nl,
        })

        if (i + 1) % 30 == 0:
            print(f"  [{i+1}/{len(all_images)}]")

    elapsed = time.time() - t0
    print(f"  Done: {len(results)} images in {elapsed:.1f}s")
    print(f"  Identical: {aug_stats['identical']}, Augmented (now aligned): {aug_stats['augmented']}, "
          f"No rob image: {aug_stats['no_rob_image']}")
    return results


def build_pdf(results):
    out_path = DOCS_DIR / "join_benchmark_report.pdf"
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=12*mm, rightMargin=12*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Body2", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=10)
    caption = ParagraphStyle("Caption", parent=styles["BodyText"], fontSize=8, leading=10,
                             textColor=colors.HexColor("#555555"), spaceAfter=4)

    elements = []

    elements.append(Paragraph("Join Strategy Benchmark Report", title_style))
    elements.append(Paragraph(
        "graph_rescue vs degree_budget_completion — 134 real images (labels aligned to augmented images)",
        body))
    elements.append(Spacer(1, 4*mm))

    total_raw = sum(r["raw_count"] for r in results)
    total_clean = sum(r["clean_count"] for r in results)
    elements.append(Paragraph(
        f"<b>Label alignment fix:</b> Using Roboflow augmented images (not originals) so bounding boxes "
        f"match label coordinates. {total_raw - total_clean} text/overlap detections removed.",
        small))
    elements.append(Spacer(1, 4*mm))

    # ── 1. Aggregate metrics ──
    elements.append(Paragraph("1. Aggregate Metrics", h2))
    metrics = [
        ("% Connected",       "pct_connected",       "%",  True),
        ("% Wires Used",      "pct_wires_used",      "%",  True),
        ("% Eff. Wires",      "pct_effective_wires", "%",  True),
        ("Floating Comps",    "floating_components",  "",   False),
        ("Self-Loops",        "self_loop_components", "",   False),
        ("Giant Nets",        "giant_nets",           "",   False),
        ("Dangling Ends",     "dangling_wire_ends",   "",   False),
        ("Unused Wires",      "unused_wires",         "",   False),
        ("Composite (↓=good)","composite",            "",   False),
        ("Join Quality (↓=good)","join_quality",      "",   False),
    ]
    header = ["Metric", "graph_rescue", "degree_budget", "Delta", "Winner"]
    rows = [header]
    for label, key, unit, higher_better in metrics:
        gr_vals = [r["gr"][key] for r in results]
        dbc_vals = [r["dbc"][key] for r in results]
        gr_avg = sum(gr_vals) / len(gr_vals)
        dbc_avg = sum(dbc_vals) / len(dbc_vals)
        delta = dbc_avg - gr_avg
        if higher_better:
            winner = "degree_budget" if delta > 0 else ("graph_rescue" if delta < 0 else "tie")
        else:
            winner = "degree_budget" if delta < 0 else ("graph_rescue" if delta > 0 else "tie")
        if unit == "%":
            rows.append([label, f"{gr_avg:.1f}%", f"{dbc_avg:.1f}%", f"{delta:+.1f}%", winner])
        else:
            rows.append([label, f"{gr_avg:.2f}", f"{dbc_avg:.2f}", f"{delta:+.2f}", winner])

    t = Table(rows, colWidths=[110, 75, 75, 60, 80])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6*mm))

    # ── 2. Per-image summary ──
    improved = sorted([r for r in results if r["dbc"]["pct_connected"] > r["gr"]["pct_connected"]],
                      key=lambda r: r["dbc"]["pct_connected"] - r["gr"]["pct_connected"], reverse=True)
    regressed = sorted([r for r in results if r["dbc"]["pct_connected"] < r["gr"]["pct_connected"]],
                       key=lambda r: r["dbc"]["pct_connected"] - r["gr"]["pct_connected"])
    same_count = len(results) - len(improved) - len(regressed)

    elements.append(Paragraph("2. Per-Image Connectivity", h2))
    elements.append(Paragraph(
        f"<b>{len(improved)}</b> improved, <b>{same_count}</b> same, <b>{len(regressed)}</b> regressed",
        body))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("Top 15 improvements:", body))
    rows2 = [["Image", "R→C", "graph_rescue", "degree_budget", "Delta"]]
    for r in improved[:15]:
        d = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
        rows2.append([r["image"], f"{r['raw_count']}→{r['clean_count']}",
                      f"{r['gr']['pct_connected']:.0f}%",
                      f"{r['dbc']['pct_connected']:.0f}%", f"+{d:.0f}%"])
    t2 = Table(rows2, colWidths=[100, 55, 75, 75, 50])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#27ae60")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 4*mm))

    if regressed:
        elements.append(Paragraph("Regressed images:", body))
        rows3 = [["Image", "R→C", "graph_rescue", "degree_budget", "Delta"]]
        for r in regressed:
            d = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
            rows3.append([r["image"], f"{r['raw_count']}→{r['clean_count']}",
                          f"{r['gr']['pct_connected']:.0f}%",
                          f"{r['dbc']['pct_connected']:.0f}%", f"{d:.0f}%"])
        t3 = Table(rows3, colWidths=[100, 55, 75, 75, 50])
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e74c3c")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"),
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))
        elements.append(t3)

    elements.append(PageBreak())

    # ── 3. Notable images ──
    elements.append(Paragraph("3. Notable Images — 3-Panel Visualization", h2))
    elements.append(Paragraph(
        "Each row: <b>Detected wires</b> (green) | <b>graph_rescue</b> (color-coded nets) "
        "| <b>degree_budget_completion</b> (color-coded nets).",
        small))
    elements.append(Spacer(1, 3*mm))

    notable_indices = set()
    for r in improved[:3]:
        notable_indices.add(results.index(r))
    for r in regressed:
        notable_indices.add(results.index(r))
    sl_delta = [(i, r["dbc"]["self_loop_components"] - r["gr"]["self_loop_components"])
                for i, r in enumerate(results)]
    sl_delta.sort(key=lambda x: -x[1])
    for idx, delta in sl_delta[:3]:
        if delta > 0:
            notable_indices.add(idx)

    for idx in sorted(notable_indices):
        r = results[idx]
        delta_conn = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
        delta_sl = r["dbc"]["self_loop_components"] - r["gr"]["self_loop_components"]

        panel = make_3panel(r["image"], r["gray"], r["wires"], r["components"],
                           r["pins"], r["gr_nl"], r["dbc_nl"])

        img_path = TMP_DIR / f"{r['image']}_3panel.png"
        cv2.imwrite(str(img_path), panel)

        img_w = 180*mm
        img_h = img_w * panel.shape[0] / panel.shape[1]
        elements.append(RLImage(str(img_path), width=img_w, height=img_h))

        tag = ""
        if delta_conn > 0:
            tag = f"[IMPROVED +{delta_conn:.0f}%]"
        elif delta_conn < 0:
            tag = f"[REGRESSED {delta_conn:.0f}%]"
        if delta_sl > 0:
            tag += f" [+{delta_sl:.0f} self-loops]"

        elements.append(Paragraph(
            f"<b>{r['image']}</b> — {r['raw_count']}→{r['clean_count']} labels | "
            f"GR: {r['gr']['pct_connected']:.0f}% conn, "
            f"{r['gr']['self_loop_components']:.0f} loops | "
            f"DBC: {r['dbc']['pct_connected']:.0f}% conn, "
            f"{r['dbc']['self_loop_components']:.0f} loops {tag}",
            caption))
        elements.append(Spacer(1, 4*mm))

    elements.append(PageBreak())

    # ── 4. Full per-image table ──
    elements.append(Paragraph("4. Full Per-Image Results", h2))
    rows4 = [["Image", "R→C", "GR %Conn", "DBC %Conn", "Δ",
              "GR Flt", "DBC Flt", "GR Lp", "DBC Lp", "GR Gnt", "DBC Gnt"]]
    for r in sorted(results, key=lambda x: x["image"]):
        d = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
        rows4.append([
            r["image"],
            f"{r['raw_count']}→{r['clean_count']}",
            f"{r['gr']['pct_connected']:.0f}",
            f"{r['dbc']['pct_connected']:.0f}",
            f"{d:+.0f}",
            f"{r['gr']['floating_components']:.0f}",
            f"{r['dbc']['floating_components']:.0f}",
            f"{r['gr']['self_loop_components']:.0f}",
            f"{r['dbc']['self_loop_components']:.0f}",
            f"{r['gr']['giant_nets']:.0f}",
            f"{r['dbc']['giant_nets']:.0f}",
        ])
    t4 = Table(rows4, colWidths=[62, 32, 36, 36, 26, 32, 32, 32, 32, 32, 32])
    ts4 = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 1.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1.5),
    ]
    for i, r in enumerate(sorted(results, key=lambda x: x["image"]), start=1):
        d = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
        if d > 0:
            ts4.append(("TEXTCOLOR", (4,i), (4,i), colors.HexColor("#27ae60")))
        elif d < 0:
            ts4.append(("TEXTCOLOR", (4,i), (4,i), colors.HexColor("#e74c3c")))
    t4.setStyle(TableStyle(ts4))
    elements.append(t4)
    elements.append(Spacer(1, 6*mm))

    # ── 5. Notes ──
    elements.append(Paragraph("5. Notes", h2))
    notes = [
        "• Labels aligned: now using Roboflow augmented images (not originals) so bounding box "
        "coordinates match the actual component positions. Previously 38/134 images had rotated/flipped "
        "augmentations causing label misalignment.",
        "• Text (cls 44) and unknown (cls 51) filtered. Overlapping detections deduplicated "
        "(optocoupler/transistor-photo, transformer/inductor, relay/switch) at IoU>0.3.",
        "• Wire usage 0% for degree_budget_completion: scoring artifact (netlist_from_uf doesn't "
        "populate n.wires).",
        "• Self-loops: two-terminal components with both pins on same net → breaks SPICE simulation.",
        "• degree_budget_completion NOT promoted to production default.",
    ]
    for note in notes:
        elements.append(Paragraph(note, small))
        elements.append(Spacer(1, 1.5*mm))

    doc.build(elements)
    print(f"PDF saved: {out_path}")
    return out_path


if __name__ == "__main__":
    results = run_benchmark()
    build_pdf(results)
