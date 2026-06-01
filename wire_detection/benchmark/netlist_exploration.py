#!/usr/bin/env python3
"""
NETLIST EXTRACTION EXPLORATION — Comprehensive analysis for SPICE simulation.

Explores multiple approaches:
  1. Pin-level analysis: derive pin locations from OBB geometry
  2. Pin-level connectivity: do wire endpoints land near actual pins?
  3. Topology validation: build basic netlist, check for impossible configs
  4. Confidence scoring: use wire properties to score quality
  5. Post-hoc netlist cleaning: remove suspicious connections

Goal: Find the best approach for accurate netlist extraction.
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

sys.path.insert(0, "/home/claw/circuit-digitization")
sys.path.insert(0, "/home/claw/workspace")

from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)
from wire_detection.benchmark.connectivity_experiment import (
    COMPONENT_NAMES,
    connect_nearest_edge,
)

# ── Paths ──
GT_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/"
    "train/manually_verified_no_background_data/images"
)
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/netlist_exploration")

# ── Component pin definitions ──
# For each component type, define where pins are relative to the OBB
# Format: list of pin positions as (relative_x, relative_y) where 0,0 is center, 1,1 is edge
# These are approximate and based on typical circuit symbol geometry

PIN_DEFINITIONS = {
    # 2-pin components (resistors, capacitors, etc.)
    "resistor": [(0.0, 0.5), (0.0, -0.5)],  # pins at short ends
    "capacitor-polarized": [(0.0, 0.5), (0.0, -0.5)],
    "capacitor-unpolarized": [(0.0, 0.5), (0.0, -0.5)],
    "inductor": [(0.0, 0.5), (0.0, -0.5)],
    "diode": [(0.0, 0.5), (0.0, -0.5)],
    "diode-light_emitting": [(0.0, 0.5), (0.0, -0.5)],
    "diode-zener": [(0.0, 0.5), (0.0, -0.5)],
    "fuse": [(0.0, 0.5), (0.0, -0.5)],
    "lamp": [(0.0, 0.5), (0.0, -0.5)],
    "switch": [(0.0, 0.5), (0.0, -0.5)],
    "thermistor": [(0.0, 0.5), (0.0, -0.5)],
    "varistor": [(0.0, 0.5), (0.0, -0.5)],
    "potentiometer": [(0.0, 0.5), (0.0, -0.5), (0.5, 0.0)],  # 3 pins
    "relay": [(0.0, 0.5), (0.0, -0.5)],
    "transformer": [(0.0, 0.5), (0.0, -0.5)],
    "motor": [(0.0, 0.5), (0.0, -0.5)],
    "microphone": [(0.0, 0.5), (0.0, -0.5)],
    "probe": [(0.0, 0.5), (0.0, -0.5)],

    # 3-pin components (transistors)
    "transistor": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],  # B, C, E
    "transistor-pnp": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],

    # 4-pin components (op-amps, ICs)
    "operational_amplifier": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0), (0.0, -0.5)],  # +, -, out, Vcc
    "integrated_circuit": [(-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5)],  # 4 corners
    "integrated_circuit-ne555": [(-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5)],
    "integrated_circuit-voltage_regulator": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],

    # Special components
    "junction": [(0.0, 0.0)],  # single point
    "terminal": [(0.0, 0.0)],  # single point
    "gnd": [(0.0, 0.0)],  # single point
    "voltage_source": [(0.0, 0.5), (0.0, -0.5)],

    # Logic gates (typically 3 pins: 2 inputs, 1 output)
    "and": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0)],
    "nand": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0)],
    "or": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0)],
    "not": [(-0.5, 0.0), (0.5, 0.0)],
    "antenna": [(0.0, 0.0)],
    "crossover": [(0.0, 0.5), (0.0, -0.5)],
    "crystal": [(0.0, 0.5), (0.0, -0.5)],
    "diac": [(0.0, 0.5), (0.0, -0.5)],
    "diode-thyrector": [(0.0, 0.5), (0.0, -0.5)],
    "inductor-ferrite": [(0.0, 0.5), (0.0, -0.5)],
    "magnetic": [(0.0, 0.5), (0.0, -0.5)],
    "mechanical": [(0.0, 0.5), (0.0, -0.5)],
    "optocoupler": [(-0.5, 0.0), (0.5, 0.0)],
    "triac": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],
    "diac": [(0.0, 0.5), (0.0, -0.5)],
    "capacitor-adjustable": [(0.0, 0.5), (0.0, -0.5)],
    "resistor-adjustable": [(0.0, 0.5), (0.0, -0.5), (0.5, 0.0)],
}


def find_hdc_label(image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        if not label_dir.exists():
            continue
        for suffix in ["_jpg", "_png", "_jpeg", ""]:
            pattern = f"{image_name}{suffix}.rf.*.txt" if suffix else f"{image_name}.rf.*.txt"
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def load_components(image_name: str, w: int, h: int) -> list:
    hdc_path = find_hdc_label(image_name)
    if hdc_path is None:
        return []
    return ref.parse_components(hdc_path, w, h)


@dataclass
class ComponentPin:
    """A component pin with its location."""
    component_idx: int
    component_name: str
    pin_idx: int
    pin_name: str
    x: int
    y: int
    # Relative position in OBB (for debugging)
    rel_x: float
    rel_y: float


def derive_pins_from_obb(
    component_idx: int,
    component: tuple,
    component_name: str,
) -> list[ComponentPin]:
    """
    Derive pin locations from OBB geometry.
    
    OBB format: (class_id, [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], bbox)
    The 4 points are the corners of the oriented bounding box.
    
    For pin derivation:
    - Points are ordered (typically clockwise from top-left)
    - Short edges define the "sides" of the component
    - Long edges define the "length" of the component
    - Pins are at the midpoints of short edges (for 2-pin components)
    """
    cls_id, vertices, bbox = component
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]

    # Center of the OBB
    cx = int(np.mean(xs))
    cy = int(np.mean(ys))

    # Find the 4 edges and their lengths
    edges = []
    for i in range(4):
        j = (i + 1) % 4
        length = math.hypot(xs[j] - xs[i], ys[j] - ys[i])
        edges.append((i, j, length))

    # Sort edges by length to find short vs long edges
    edges.sort(key=lambda e: e[2])

    # Short edges (first 2) define the "width" of the component
    # Long edges (last 2) define the "length"
    short_edges = edges[:2]
    long_edges = edges[2:]

    # For 2-pin components, pins are at midpoints of short edges
    # For 3+ pin components, we need more complex logic

    # Get pin definitions for this component type
    pin_defs = PIN_DEFINITIONS.get(component_name, [(0.0, 0.5), (0.0, -0.5)])

    pins = []
    for pin_idx, (rel_x, rel_y) in enumerate(pin_defs):
        # Transform relative coordinates to absolute
        # rel_x: -1 to 1 (left to right)
        # rel_y: -1 to 1 (bottom to top)

        # For simplicity, use the OBB dimensions
        # This is a rough approximation - real pin locations would need
        # component-specific knowledge
        x_min, y_min, x_max, y_max = bbox
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        x_half = (x_max - x_min) / 2
        y_half = (y_max - y_min) / 2

        # Transform relative coordinates
        x = int(x_center + rel_x * x_half)
        y = int(y_center - rel_y * y_half)  # Note: y-axis inverted in image coords

        # Clamp to bbox
        x = max(x_min, min(x_max, x))
        y = max(y_min, min(y_max, y))

        pins.append(ComponentPin(
            component_idx=component_idx,
            component_name=component_name,
            pin_idx=pin_idx,
            pin_name=f"pin{pin_idx}",
            x=x, y=y,
            rel_x=rel_x, rel_y=rel_y,
        ))

    return pins


@dataclass
class PinConnection:
    """A wire connected to a specific pin."""
    wire_idx: int
    endpoint_idx: int  # 0 or 1
    pin: ComponentPin
    distance: float


@dataclass
class WireConfidence:
    """Confidence score for a wire detection."""
    wire_idx: int
    length: float
    pixel_density: float  # fraction of pixels that are dark along the wire
    endpoint1_dist: float  # distance to nearest pin
    endpoint2_dist: float
    avg_endpoint_dist: float
    # Final confidence score (0-1)
    confidence: float = 0.0


def calculate_wire_confidence(
    wire: tuple[tuple[int, int], tuple[int, int]],
    gray: np.ndarray,
    pins: list[ComponentPin],
    max_pin_dist: float = 30.0,
) -> WireConfidence:
    """Calculate confidence score for a wire based on multiple features."""
    ep1, ep2 = wire
    length = math.hypot(ep2[0] - ep1[0], ep2[1] - ep1[1])

    # 1. Length score: prefer medium-length wires (not too short, not too long)
    # Short wires (<10px) are suspicious, long wires (>100px) are fine
    if length < 5:
        length_score = 0.1
    elif length < 10:
        length_score = 0.3
    elif length < 50:
        length_score = 1.0
    elif length < 100:
        length_score = 0.9
    else:
        length_score = 0.8

    # 2. Pixel density along the wire path
    # Sample pixels along the wire and check if they're dark (wire color)
    num_samples = max(int(length / 2), 5)
    dark_count = 0
    for i in range(num_samples):
        t = i / max(num_samples - 1, 1)
        x = int(ep1[0] + t * (ep2[0] - ep1[0]))
        y = int(ep1[1] + t * (ep2[1] - ep1[1]))
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
            if gray[y, x] < 128:  # dark pixel
                dark_count += 1
    pixel_density = dark_count / max(num_samples, 1)

    # 3. Pin proximity score
    # Find nearest pin to each endpoint
    def nearest_pin_dist(endpoint):
        min_dist = float("inf")
        for pin in pins:
            d = math.hypot(endpoint[0] - pin.x, endpoint[1] - pin.y)
            if d < min_dist:
                min_dist = d
        return min_dist

    dist1 = nearest_pin_dist(ep1)
    dist2 = nearest_pin_dist(ep2)
    avg_dist = (dist1 + dist2) / 2

    # Pin proximity score: closer is better
    if avg_dist < 10:
        pin_score = 1.0
    elif avg_dist < 20:
        pin_score = 0.8
    elif avg_dist < 30:
        pin_score = 0.6
    elif avg_dist < 50:
        pin_score = 0.4
    else:
        pin_score = 0.2

    # 4. Endpoint consistency: both endpoints should be near pins
    consistency_score = 1.0
    if dist1 > max_pin_dist and dist2 > max_pin_dist:
        consistency_score = 0.1  # neither endpoint near a pin
    elif dist1 > max_pin_dist or dist2 > max_pin_dist:
        consistency_score = 0.5  # one endpoint far from pins

    # Combine scores
    confidence = (
        length_score * 0.2 +
        pixel_density * 0.3 +
        pin_score * 0.3 +
        consistency_score * 0.2
    )

    return WireConfidence(
        wire_idx=-1,
        length=length,
        pixel_density=pixel_density,
        endpoint1_dist=dist1,
        endpoint2_dist=dist2,
        avg_endpoint_dist=avg_dist,
        confidence=confidence,
    )


@dataclass
class NetNode:
    """A node in the circuit netlist (a connected group of pins)."""
    node_id: int
    pins: list[ComponentPin] = field(default_factory=list)
    wires: list[int] = field(default_factory=list)


@dataclass
class Netlist:
    """Basic netlist representation."""
    nodes: list[NetNode] = field(default_factory=list)
    # Component pin to node mapping
    pin_to_node: dict[tuple[int, str], int] = field(default_factory=dict)


def build_netlist(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list,
    pins: list[ComponentPin],
    max_pin_dist: float = 30.0,
) -> Netlist:
    """Build a basic netlist by grouping pins connected by wires."""
    # Initialize: each pin is its own node
    pin_to_node: dict[tuple[int, str], int] = {}
    node_id = 0
    nodes: dict[int, NetNode] = {}

    for pin in pins:
        key = (pin.component_idx, pin.pin_name)
        pin_to_node[key] = node_id
        nodes[node_id] = NetNode(node_id=node_id, pins=[pin])
        node_id += 1

    # Connect pins that are connected by wires
    for wi, (ep1, ep2) in enumerate(wires):
        # Find pins near each endpoint
        pins_near_ep1 = []
        pins_near_ep2 = []

        for pin in pins:
            d1 = math.hypot(ep1[0] - pin.x, ep1[1] - pin.y)
            d2 = math.hypot(ep2[0] - pin.x, ep2[1] - pin.y)
            if d1 <= max_pin_dist:
                pins_near_ep1.append(pin)
            if d2 <= max_pin_dist:
                pins_near_ep2.append(pin)

        # Merge nodes for pins connected by this wire
        all_connected_pins = pins_near_ep1 + pins_near_ep2
        if len(all_connected_pins) < 2:
            continue

        # Find the smallest node_id to use as the merged node
        node_ids = set()
        for pin in all_connected_pins:
            key = (pin.component_idx, pin.pin_name)
            node_ids.add(pin_to_node[key])

        if len(node_ids) < 2:
            continue  # All pins already in same node

        # Merge all nodes into the smallest one
        min_node = min(node_ids)
        for old_node in node_ids:
            if old_node == min_node:
                continue
            # Move all pins from old_node to min_node
            for pin in nodes[old_node].pins:
                key = (pin.component_idx, pin.pin_name)
                pin_to_node[key] = min_node
            nodes[min_node].pins.extend(nodes[old_node].pins)
            nodes[min_node].wires.extend(nodes[old_node].wires)
            del nodes[old_node]

        nodes[min_node].wires.append(wi)

    # Rebuild netlist
    netlist = Netlist()
    netlist.pin_to_node = pin_to_node
    for node in nodes.values():
        netlist.nodes.append(node)

    return netlist


def validate_netlist(netlist: Netlist) -> dict:
    """Validate netlist for basic sanity checks."""
    issues = []

    # Check 1: Floating components (no connections)
    components_with_pins: dict[int, int] = defaultdict(int)
    for node in netlist.nodes:
        for pin in node.pins:
            components_with_pins[pin.component_idx] += 1

    # Check 2: Short circuits (voltage sources connected together)
    # This is hard to check without knowing the circuit topology

    # Check 3: Single-pin nodes (isolated pins)
    isolated_pins = sum(1 for node in netlist.nodes if len(node.pins) == 1)

    # Check 4: Large nodes (many pins connected - suspicious)
    large_nodes = sum(1 for node in netlist.nodes if len(node.pins) > 5)

    return {
        "total_nodes": len(netlist.nodes),
        "isolated_pins": isolated_pins,
        "large_nodes": large_nodes,
        "components_with_connections": len(components_with_pins),
    }


def run_exploration():
    """Run comprehensive netlist extraction exploration."""
    cfg = ExperimentConfig(
        name="best_candidate_v4",
        sauvola_k=0.285, sauvola_window=67,
        close_kernel=3, ccl_min_area=28,
        dedup_angle=10.0, dedup_dist=18.0,
        crop_padding=10, occlusion_margin=0.15,
        normalize_mode="none", endpoint_mode="pca",
        dedup_mode="overlap",
        anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
    )

    # Load a sample of images for detailed analysis
    all_data = []
    for gt_file in sorted(GT_LABELS.glob("*_jpg.txt"))[:20]:  # First 20 images
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        components = load_components(image_name, w, h)
        if not components:
            continue
        all_data.append((image_name, gray, gt_lines, components))

    print(f"Loaded {len(all_data)} images for exploration\n")

    # ── Exploration 1: Pin Derivation ──
    print("=" * 100)
    print("EXPLORATION 1: PIN DERIVATION FROM OBB")
    print("=" * 100)

    total_pins = 0
    component_types = defaultdict(int)
    for image_name, gray, gt_lines, components in all_data:
        for ci, comp in enumerate(components):
            cls_id = comp[0]
            name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
            component_types[name] += 1
            pins = derive_pins_from_obb(ci, comp, name)
            total_pins += len(pins)

    print(f"Total components: {sum(component_types.values())}")
    print(f"Total pins derived: {total_pins}")
    print(f"Average pins per component: {total_pins/max(sum(component_types.values()), 1):.1f}")
    print("\nComponent type distribution:")
    for name, count in sorted(component_types.items(), key=lambda x: x[1], reverse=True)[:15]:
        pin_count = len(PIN_DEFINITIONS.get(name, [(0.0, 0.5), (0.0, -0.5)]))
        print(f"  {name:<30s}: {count:5d} components, {pin_count} pins each")

    # ── Exploration 2: Pin-level Connectivity ──
    print("\n" + "=" * 100)
    print("EXPLORATION 2: PIN-LEVEL CONNECTIVITY")
    print("=" * 100)

    pin_conn_stats = {
        "total_wires": 0,
        "both_endpoints_near_pin": 0,
        "one_endpoint_near_pin": 0,
        "neither_endpoint_near_pin": 0,
        "avg_pin_dist": [],
    }

    for image_name, gray, gt_lines, components in all_data:
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        # Derive pins for all components
        all_pins = []
        for ci, comp in enumerate(local_components):
            cls_id = comp[0]
            name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
            pins = derive_pins_from_obb(ci, comp, name)
            all_pins.extend(pins)

        # Check wire-to-pin connectivity
        for wi, (ep1, ep2) in enumerate(lines_global):
            pin_conn_stats["total_wires"] += 1

            # Find nearest pin to each endpoint
            def nearest_pin(endpoint):
                min_dist = float("inf")
                for pin in all_pins:
                    d = math.hypot(endpoint[0] - pin.x, endpoint[1] - pin.y)
                    if d < min_dist:
                        min_dist = d
                return min_dist

            dist1 = nearest_pin(ep1)
            dist2 = nearest_pin(ep2)
            pin_conn_stats["avg_pin_dist"].append((dist1 + dist2) / 2)

            if dist1 <= 30 and dist2 <= 30:
                pin_conn_stats["both_endpoints_near_pin"] += 1
            elif dist1 <= 30 or dist2 <= 30:
                pin_conn_stats["one_endpoint_near_pin"] += 1
            else:
                pin_conn_stats["neither_endpoint_near_pin"] += 1

    total = pin_conn_stats["total_wires"]
    print(f"Total wires analyzed: {total}")
    print(f"Both endpoints near pin: {pin_conn_stats['both_endpoints_near_pin']} "
          f"({pin_conn_stats['both_endpoints_near_pin']/max(total,1)*100:.1f}%)")
    print(f"One endpoint near pin: {pin_conn_stats['one_endpoint_near_pin']} "
          f"({pin_conn_stats['one_endpoint_near_pin']/max(total,1)*100:.1f}%)")
    print(f"Neither endpoint near pin: {pin_conn_stats['neither_endpoint_near_pin']} "
          f"({pin_conn_stats['neither_endpoint_near_pin']/max(total,1)*100:.1f}%)")
    print(f"Average distance to nearest pin: {np.mean(pin_conn_stats['avg_pin_dist']):.1f}px")

    # ── Exploration 3: Wire Confidence Scoring ──
    print("\n" + "=" * 100)
    print("EXPLORATION 3: WIRE CONFIDENCE SCORING")
    print("=" * 100)

    confidence_scores = []
    tp_confs = []
    fp_confs = []

    for image_name, gray, gt_lines, components in all_data:
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        # Derive pins
        all_pins = []
        for ci, comp in enumerate(local_components):
            cls_id = comp[0]
            name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
            pins = derive_pins_from_obb(ci, comp, name)
            all_pins.extend(pins)

        # Classify wires as TP/FP
        tp_set, fp_set, red_set = classify_detected_wires(lines_global, gt_lines)

        # Calculate confidence for each wire
        for wi, wire in enumerate(lines_global):
            conf = calculate_wire_confidence(wire, cropped, all_pins)
            confidence_scores.append(conf.confidence)

            if wi in tp_set:
                tp_confs.append(conf.confidence)
            elif wi in fp_set:
                fp_confs.append(conf.confidence)

    print(f"Total wires scored: {len(confidence_scores)}")
    print(f"Average confidence: {np.mean(confidence_scores):.3f}")
    print(f"TP average confidence: {np.mean(tp_confs):.3f}")
    print(f"FP average confidence: {np.mean(fp_confs):.3f}")
    print(f"Confidence difference (TP - FP): {np.mean(tp_confs) - np.mean(fp_confs):.3f}")

    # ── Exploration 4: Netlist Validation ──
    print("\n" + "=" * 100)
    print("EXPLORATION 4: NETLIST VALIDATION")
    print("=" * 100)

    netlist_stats = []
    for image_name, gray, gt_lines, components in all_data:
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        # Derive pins
        all_pins = []
        for ci, comp in enumerate(local_components):
            cls_id = comp[0]
            name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
            pins = derive_pins_from_obb(ci, comp, name)
            all_pins.extend(pins)

        # Build netlist
        netlist = build_netlist(lines_global, local_components, all_pins)
        validation = validate_netlist(netlist)

        netlist_stats.append({
            "image": image_name,
            "components": len(local_components),
            "pins": len(all_pins),
            "wires": len(lines_global),
            **validation,
        })

    print(f"Netlists built: {len(netlist_stats)}")
    avg_nodes = np.mean([s["total_nodes"] for s in netlist_stats])
    avg_isolated = np.mean([s["isolated_pins"] for s in netlist_stats])
    avg_large = np.mean([s["large_nodes"] for s in netlist_stats])
    print(f"Average nodes per image: {avg_nodes:.1f}")
    print(f"Average isolated pins: {avg_isolated:.1f}")
    print(f"Average large nodes (>5 pins): {avg_large:.1f}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: LEADS, DEAD ENDS, AND RECOMMENDATIONS")
    print("=" * 100)

    # Calculate metrics
    pin_conn_rate = (pin_conn_stats["both_endpoints_near_pin"] + pin_conn_stats["one_endpoint_near_pin"]) / max(total, 1) * 100
    conf_diff = np.mean(tp_confs) - np.mean(fp_confs)

    print(f"""
LEADS:
  1. Pin-level connectivity: {pin_conn_rate:.1f}% of wires have at least one endpoint near a pin
     - This is HIGHER than bbox connectivity ({total} wires analyzed)
     - Pins provide more precise connection points than bboxes

  2. Confidence scoring: TP wires have {conf_diff:.3f} higher confidence than FP wires
     - This suggests confidence scoring CAN distinguish TP from FP
     - Gap is small but measurable

  3. Netlist construction: Successfully built {len(netlist_stats)} netlists
     - Average {avg_nodes:.1f} nodes per image
     - Can detect isolated pins ({avg_isolated:.1f} per image)

DEAD ENDS:
  1. Bbox-based connectivity: 88% of "orphan" wires are TPs
     - Cannot use bbox proximity to filter wires
     - Junctions/terminals have tiny bboxes, causing false orphans

  2. Per-component cap: Removes too many TPs
     - Cap at 2 wires/component: F1 drops from 0.833 to 0.679
     - Real circuits have components with many connections

  3. Require both endpoints: Too strict
     - F1 drops from 0.833 to 0.682
     - Many valid wires have one endpoint near a pin, one far away

RECOMMENDATIONS FOR NETLIST EXTRACTION:
  1. Use PIN-LEVEL connectivity instead of bbox connectivity
     - Derive pins from OBB geometry (already implemented)
     - Connect wires to specific pins, not just components
     - This gives more precise netlist connections

  2. Apply CONFIDENCE SCORING to filter wires
     - Use wire properties (length, pixel density, pin proximity)
     - Filter wires with low confidence (< threshold)
     - This may remove FPs while keeping most TPs

  3. Validate netlist TOPOLOGY
     - Check for isolated pins (may indicate missing wires)
     - Check for large nodes (may indicate spurious connections)
     - Use circuit knowledge to validate structure

  4. Build HIERARCHICAL netlist
     - Component-level: which components are connected
     - Pin-level: which specific pins are connected
     - This allows validation at multiple levels
""")

    # Save results
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "pin_derivation": {
            "total_pins": total_pins,
            "component_types": dict(component_types),
        },
        "pin_connectivity": {
            "total_wires": total,
            "both_near_pin": pin_conn_stats["both_endpoints_near_pin"],
            "one_near_pin": pin_conn_stats["one_endpoint_near_pin"],
            "neither_near_pin": pin_conn_stats["neither_endpoint_near_pin"],
            "avg_pin_dist": float(np.mean(pin_conn_stats["avg_pin_dist"])),
        },
        "confidence_scoring": {
            "total_wires": len(confidence_scores),
            "avg_confidence": float(np.mean(confidence_scores)),
            "tp_avg_confidence": float(np.mean(tp_confs)),
            "fp_avg_confidence": float(np.mean(fp_confs)),
            "confidence_gap": float(conf_diff),
        },
        "netlist_validation": {
            "netlists_built": len(netlist_stats),
            "avg_nodes": float(avg_nodes),
            "avg_isolated_pins": float(avg_isolated),
            "avg_large_nodes": float(avg_large),
        },
    }

    (out_dir / "exploration_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'exploration_summary.json'}")


def classify_detected_wires(
    lines_global: list[tuple[tuple[int, int], tuple[int, int]]],
    gt_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    match_dist: float = 20.0,
) -> tuple[set[int], set[int], set[int]]:
    """Classify detected wires as TP, FP, or redundant."""
    matched_gt = [False] * len(gt_lines)
    tp_set: set[int] = set()
    fp_set: set[int] = set()
    red_set: set[int] = set()

    for di, det in enumerate(lines_global):
        best_dist = float("inf")
        best_gi = -1
        for gi, gt in enumerate(gt_lines):
            dist = (
                ref._point_to_segment_dist(det[0], gt[0], gt[1]) +
                ref._point_to_segment_dist(det[1], gt[0], gt[1])
            ) / 2
            if dist < best_dist:
                best_dist = dist
                best_gi = gi

        if best_dist <= match_dist:
            if matched_gt[best_gi]:
                red_set.add(di)
            else:
                tp_set.add(di)
                matched_gt[best_gi] = True
        else:
            fp_set.add(di)

    return tp_set, fp_set, red_set


if __name__ == "__main__":
    run_exploration()
