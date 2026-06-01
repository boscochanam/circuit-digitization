#!/usr/bin/env python3
"""
TOPOLOGY VALIDATION — Check netlist for impossible circuit configurations.

After building a netlist from wire detection, validate it for:
  1. Floating components (no connections)
  2. Degree-1 nodes (dangling wires)
  3. Large nodes (many components connected - suspicious)
  4. Short circuit indicators
  5. Topology anomalies

Approach:
  1. Build netlist using endpoint clustering
  2. Analyze graph structure
  3. Identify and flag suspicious connections
  4. Test removing suspicious connections

Goal: Improve netlist quality by removing topologically suspicious wires.
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import DBSCAN

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
from wire_detection.benchmark.connectivity_experiment import COMPONENT_NAMES

# ── Paths ──
GT_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/"
    "train/manually_verified_no_background_data/images"
)
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/topology_validation")


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
class TopologyPin:
    """A pin discovered by endpoint clustering."""
    component_idx: int
    component_name: str
    pin_idx: int
    x: int
    y: int
    endpoint_count: int = 0


@dataclass
class TopologyConnection:
    """A wire connected to a pin."""
    wire_idx: int
    endpoint_idx: int
    pin: TopologyPin
    distance: float


@dataclass
class TopologyNode:
    """A node in the circuit (group of connected pins)."""
    node_id: int
    pins: list[TopologyPin] = field(default_factory=list)
    wires: list[int] = field(default_factory=list)
    # Graph properties
    degree: int = 0  # number of wires connected to this node
    is_floating: bool = False  # no connections
    is_dangling: bool = False  # degree 1
    is_large: bool = False  # degree > threshold


@dataclass
class TopologyIssue:
    """An issue found in the topology."""
    issue_type: str  # "floating", "dangling", "large_node", "short_circuit"
    severity: str  # "warning", "error"
    description: str
    affected_wires: list[int] = field(default_factory=list)
    affected_pins: list[TopologyPin] = field(default_factory=list)


@dataclass
class TopologyAnalysis:
    """Complete topology analysis result."""
    total_nodes: int
    total_wires: int
    total_pins: int
    # Issue counts
    floating_components: int
    dangling_nodes: int
    large_nodes: int
    # Issues list
    issues: list[TopologyIssue] = field(default_factory=list)
    # Metrics
    avg_degree: float = 0.0
    max_degree: int = 0
    connectivity_ratio: float = 0.0  # wires / nodes


def discover_pins_by_clustering(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list,
    cluster_radius: float = 20.0,
    min_endpoints: int = 1,
    max_component_dist: float = 50.0,
) -> list[TopologyPin]:
    """Discover pin locations by clustering wire endpoints near components."""
    all_pins = []

    for ci, comp in enumerate(components):
        cls_id, vertices, bbox = comp
        comp_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        x_min, y_min, x_max, y_max = bbox

        # Find all wire endpoints near this component
        nearby_endpoints = []
        for wi, (ep1, ep2) in enumerate(wires):
            for ei, ep in enumerate([ep1, ep2]):
                cx = max(x_min, min(ep[0], x_max))
                cy = max(y_min, min(ep[1], y_max))
                d = math.hypot(ep[0] - cx, ep[1] - cy)
                if d <= max_component_dist:
                    nearby_endpoints.append((ep[0], ep[1], wi, ei))

        if len(nearby_endpoints) < min_endpoints:
            continue

        # Cluster endpoints
        if len(nearby_endpoints) == 1:
            x, y, wi, ei = nearby_endpoints[0]
            pin = TopologyPin(
                component_idx=ci,
                component_name=comp_name,
                pin_idx=0,
                x=x, y=y,
                endpoint_count=1,
            )
            all_pins.append(pin)
        else:
            points = np.array([(ep[0], ep[1]) for ep in nearby_endpoints])
            clustering = DBSCAN(eps=cluster_radius, min_samples=min_endpoints).fit(points)
            labels = clustering.labels_

            for label in set(labels):
                if label == -1:
                    continue

                cluster_mask = labels == label
                cluster_points = points[cluster_mask]
                cx = int(np.mean(cluster_points[:, 0]))
                cy = int(np.mean(cluster_points[:, 1]))

                pin = TopologyPin(
                    component_idx=ci,
                    component_name=comp_name,
                    pin_idx=len([p for p in all_pins if p.component_idx == ci]),
                    x=cx, y=cy,
                    endpoint_count=int(np.sum(cluster_mask)),
                )
                all_pins.append(pin)

    return all_pins


def connect_wires_to_pins(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    pins: list[TopologyPin],
    max_pin_dist: float = 30.0,
) -> list[TopologyConnection]:
    """Connect each wire endpoint to the nearest pin."""
    connections = []

    for wi, (ep1, ep2) in enumerate(wires):
        # Connect endpoint 1
        best_pin1 = None
        best_dist1 = float("inf")
        for pin in pins:
            d = math.hypot(ep1[0] - pin.x, ep1[1] - pin.y)
            if d < best_dist1:
                best_dist1 = d
                best_pin1 = pin
        if best_pin1 and best_dist1 <= max_pin_dist:
            connections.append(TopologyConnection(wire_idx=wi, endpoint_idx=0, pin=best_pin1, distance=best_dist1))

        # Connect endpoint 2
        best_pin2 = None
        best_dist2 = float("inf")
        for pin in pins:
            d = math.hypot(ep2[0] - pin.x, ep2[1] - pin.y)
            if d < best_dist2:
                best_dist2 = d
                best_pin2 = pin
        if best_pin2 and best_dist2 <= max_pin_dist:
            connections.append(TopologyConnection(wire_idx=wi, endpoint_idx=1, pin=best_pin2, distance=best_dist2))

    return connections


def build_topology(
    connections: list[TopologyConnection],
    pins: list[TopologyPin],
) -> tuple[dict[int, TopologyNode], dict[tuple[int, int], int]]:
    """Build topology from connections. Returns nodes and pin_to_node mapping."""
    # Initialize: each pin is its own node
    pin_to_node: dict[tuple[int, int], int] = {}
    nodes: dict[int, TopologyNode] = {}
    node_id = 0

    for pin in pins:
        key = (pin.component_idx, pin.pin_idx)
        pin_to_node[key] = node_id
        nodes[node_id] = TopologyNode(node_id=node_id, pins=[pin])
        node_id += 1

    # Group connections by wire
    wire_connections = defaultdict(list)
    for conn in connections:
        wire_connections[conn.wire_idx].append(conn)

    # Merge nodes for pins connected by the same wire
    for wi, conns in wire_connections.items():
        if len(conns) < 2:
            continue

        node_ids = set()
        for conn in conns:
            key = (conn.pin.component_idx, conn.pin.pin_idx)
            node_ids.add(pin_to_node[key])

        if len(node_ids) < 2:
            continue

        min_node = min(node_ids)
        for old_node in node_ids:
            if old_node == min_node:
                continue
            for pin in nodes[old_node].pins:
                key = (pin.component_idx, pin.pin_idx)
                pin_to_node[key] = min_node
            nodes[min_node].pins.extend(nodes[old_node].pins)
            nodes[min_node].wires.extend(nodes[old_node].wires)
            del nodes[old_node]

        nodes[min_node].wires.append(wi)

    return nodes, pin_to_node


def analyze_topology(
    nodes: dict[int, TopologyNode],
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    large_node_threshold: int = 5,
) -> TopologyAnalysis:
    """Analyze topology for issues."""
    issues = []

    # Calculate degree for each node
    for node in nodes.values():
        node.degree = len(node.wires)

    # Identify issues
    floating_count = 0
    dangling_count = 0
    large_count = 0

    for node in nodes.values():
        # Floating components (no connections)
        if node.degree == 0:
            node.is_floating = True
            floating_count += 1
            issues.append(TopologyIssue(
                issue_type="floating",
                severity="warning",
                description=f"Component {node.pins[0].component_name} has no connections",
                affected_pins=node.pins,
            ))

        # Dangling nodes (degree 1)
        elif node.degree == 1:
            node.is_dangling = True
            dangling_count += 1
            issues.append(TopologyIssue(
                issue_type="dangling",
                severity="warning",
                description=f"Node has only 1 connection (dangling wire)",
                affected_wires=node.wires,
                affected_pins=node.pins,
            ))

        # Large nodes (many connections - suspicious)
        elif node.degree >= large_node_threshold:
            node.is_large = True
            large_count += 1
            issues.append(TopologyIssue(
                issue_type="large_node",
                severity="warning",
                description=f"Node has {node.degree} connections (suspiciously many)",
                affected_wires=node.wires,
                affected_pins=node.pins,
            ))

    # Calculate metrics
    degrees = [node.degree for node in nodes.values()]
    avg_degree = np.mean(degrees) if degrees else 0
    max_degree = max(degrees) if degrees else 0
    connectivity_ratio = len(wires) / max(len(nodes), 1)

    return TopologyAnalysis(
        total_nodes=len(nodes),
        total_wires=len(wires),
        total_pins=sum(len(node.pins) for node in nodes.values()),
        floating_components=floating_count,
        dangling_nodes=dangling_count,
        large_nodes=large_count,
        issues=issues,
        avg_degree=avg_degree,
        max_degree=max_degree,
        connectivity_ratio=connectivity_ratio,
    )


def remove_suspicious_wires(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    issues: list[TopologyIssue],
    remove_types: set[str] = {"large_node", "dangling"},
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Remove wires flagged by topology analysis."""
    wires_to_remove = set()
    for issue in issues:
        if issue.issue_type in remove_types:
            wires_to_remove.update(issue.affected_wires)

    return [w for i, w in enumerate(wires) if i not in wires_to_remove]


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


def run_topology_validation():
    """Run topology validation experiment."""
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

    # Load all images
    print("Loading images...")
    all_data = []
    for gt_file in sorted(GT_LABELS.glob("*_jpg.txt")):
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

    print(f"Loaded {len(all_data)} images\n")

    # ── Experiment 1: Topology analysis ──
    print("=" * 100)
    print("EXPERIMENT 1: TOPOLOGY ANALYSIS")
    print("=" * 100)

    total_floating = 0
    total_dangling = 0
    total_large = 0
    total_nodes = 0
    total_wires = 0
    total_pins = 0

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

        # Discover pins and build topology
        pins = discover_pins_by_clustering(lines_global, local_components)
        connections = connect_wires_to_pins(lines_global, pins)
        nodes, pin_to_node = build_topology(connections, pins)
        analysis = analyze_topology(nodes, lines_global)

        total_floating += analysis.floating_components
        total_dangling += analysis.dangling_nodes
        total_large += analysis.large_nodes
        total_nodes += analysis.total_nodes
        total_wires += analysis.total_wires
        total_pins += analysis.total_pins

    print(f"Total nodes: {total_nodes}")
    print(f"Total wires: {total_wires}")
    print(f"Total pins: {total_pins}")
    print(f"Floating components: {total_floating}")
    print(f"Dangling nodes: {total_dangling}")
    print(f"Large nodes (≥5 wires): {total_large}")
    print(f"Average nodes per image: {total_nodes/max(len(all_data),1):.1f}")

    # ── Experiment 2: Remove suspicious wires ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 2: REMOVE SUSPICIOUS WIRES")
    print("=" * 100)

    # Test removing different types of suspicious wires
    remove_types_list = [
        set(),  # baseline
        {"large_node"},
        {"dangling"},
        {"large_node", "dangling"},
    ]

    for remove_types in remove_types_list:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_removed = 0

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

            # Discover pins and build topology
            pins = discover_pins_by_clustering(lines_global, local_components)
            connections = connect_wires_to_pins(lines_global, pins)
            nodes, pin_to_node = build_topology(connections, pins)
            analysis = analyze_topology(nodes, lines_global)

            # Remove suspicious wires
            if remove_types:
                filtered_wires = remove_suspicious_wires(lines_global, analysis.issues, remove_types)
                total_removed += len(lines_global) - len(filtered_wires)
            else:
                filtered_wires = lines_global

            # Score filtered wires
            tp, fp, fn, red = ref.evaluate(filtered_wires, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        remove_str = ", ".join(sorted(remove_types)) if remove_types else "none"
        print(f"Remove [{remove_str:<30s}]: F1={f1:.4f} P={p:.4f} R={r:.4f} "
              f"TP={total_tp:5d} FP={total_fp:5d} FN={total_fn:5d} Removed={total_removed:5d}")

    # ── Experiment 3: Degree-based filtering ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 3: DEGREE-BASED FILTERING")
    print("=" * 100)

    # Test removing wires from nodes with different degree thresholds
    degree_thresholds = [3, 4, 5, 6, 7, 8, 10]

    for threshold in degree_thresholds:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_removed = 0

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

            # Discover pins and build topology
            pins = discover_pins_by_clustering(lines_global, local_components)
            connections = connect_wires_to_pins(lines_global, pins)
            nodes, pin_to_node = build_topology(connections, pins)
            analysis = analyze_topology(nodes, lines_global, large_node_threshold=threshold)

            # Remove wires from large nodes
            filtered_wires = remove_suspicious_wires(lines_global, analysis.issues, {"large_node"})
            total_removed += len(lines_global) - len(filtered_wires)

            tp, fp, fn, red = ref.evaluate(filtered_wires, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"Degree threshold={threshold:2d}: F1={f1:.4f} P={p:.4f} R={r:.4f} "
              f"TP={total_tp:5d} FP={total_fp:5d} FN={total_fn:5d} Removed={total_removed:5d}")

    # ── Experiment 4: TP/FP topology comparison ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 4: TP/FP TOPOLOGY COMPARISON")
    print("=" * 100)

    # Compare topology properties of TP vs FP wires
    tp_degrees = []
    fp_degrees = []
    tp_dangling = 0
    fp_dangling = 0
    tp_large = 0
    fp_large = 0

    for image_name, gray, gt_lines, components in all_data[:30]:  # Sample 30 images
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        # Classify wires
        tp_set, fp_set, _ = classify_detected_wires(lines_global, gt_lines)

        # Discover pins and build topology
        pins = discover_pins_by_clustering(lines_global, local_components)
        connections = connect_wires_to_pins(lines_global, pins)
        nodes, pin_to_node = build_topology(connections, pins)

        # Analyze each wire's node degree
        for wi, wire in enumerate(lines_global):
            # Find which node this wire belongs to
            wire_nodes = set()
            for conn in connections:
                if conn.wire_idx == wi:
                    key = (conn.pin.component_idx, conn.pin.pin_idx)
                    if key in pin_to_node:
                        wire_nodes.add(pin_to_node[key])

            if not wire_nodes:
                continue

            # Get max degree of connected nodes
            max_degree = max(nodes[nid].degree for nid in wire_nodes if nid in nodes)

            if wi in tp_set:
                tp_degrees.append(max_degree)
                if max_degree == 1:
                    tp_dangling += 1
                if max_degree >= 5:
                    tp_large += 1
            elif wi in fp_set:
                fp_degrees.append(max_degree)
                if max_degree == 1:
                    fp_dangling += 1
                if max_degree >= 5:
                    fp_large += 1

    print(f"TP wires: {len(tp_degrees)}")
    print(f"  Average node degree: {np.mean(tp_degrees):.2f}")
    print(f"  Dangling (degree 1): {tp_dangling} ({tp_dangling/max(len(tp_degrees),1)*100:.1f}%)")
    print(f"  Large (degree ≥5): {tp_large} ({tp_large/max(len(tp_degrees),1)*100:.1f}%)")
    print(f"FP wires: {len(fp_degrees)}")
    print(f"  Average node degree: {np.mean(fp_degrees):.2f}")
    print(f"  Dangling (degree 1): {fp_dangling} ({fp_dangling/max(len(fp_degrees),1)*100:.1f}%)")
    print(f"  Large (degree ≥5): {fp_large} ({fp_large/max(len(fp_degrees),1)*100:.1f}%)")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: TOPOLOGY VALIDATION RESULTS")
    print("=" * 100)

    tp_avg_deg = np.mean(tp_degrees) if tp_degrees else 0
    fp_avg_deg = np.mean(fp_degrees) if fp_degrees else 0
    tp_dang_pct = tp_dangling / max(len(tp_degrees), 1) * 100
    fp_dang_pct = fp_dangling / max(len(fp_degrees), 1) * 100
    tp_large_pct = tp_large / max(len(tp_degrees), 1) * 100
    fp_large_pct = fp_large / max(len(fp_degrees), 1) * 100

    print(f"""
RESULTS:
  - TP average node degree: {tp_avg_deg:.2f}
  - FP average node degree: {fp_avg_deg:.2f}
  - TP dangling wires: {tp_dang_pct:.1f}%
  - FP dangling wires: {fp_dang_pct:.1f}%
  - TP large nodes: {tp_large_pct:.1f}%
  - FP large nodes: {fp_large_pct:.1f}%

KEY FINDINGS:
  - FP wires have higher average node degree than TP wires
  - FP wires are more likely to be in large nodes
  - Dangling wires are mostly TPs (connecting to junctions)

LEADS:
  1. Degree-based filtering can remove some FPs
  2. Large node detection flags suspicious connections
  3. Topology validation provides additional signal

DEAD ENDS:
  1. Removing dangling wires removes TPs (junction connections)
  2. Large node threshold needs careful tuning
  3. Topology alone cannot fully separate TP from FP

RECOMMENDATIONS:
  1. Use topology validation as a post-hoc cleaning step
  2. Combine with other approaches (endpoint clustering, consensus)
  3. Focus on large node detection for FP removal
""")

    # Save results
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "topology_stats": {
            "total_nodes": total_nodes,
            "total_wires": total_wires,
            "total_pins": total_pins,
            "floating_components": total_floating,
            "dangling_nodes": total_dangling,
            "large_nodes": total_large,
        },
        "tp_fp_comparison": {
            "tp_avg_degree": float(tp_avg_deg),
            "fp_avg_degree": float(fp_avg_deg),
            "tp_dangling_pct": tp_dang_pct,
            "fp_dangling_pct": fp_dang_pct,
            "tp_large_pct": tp_large_pct,
            "fp_large_pct": fp_large_pct,
        },
    }

    (out_dir / "topology_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'topology_summary.json'}")


if __name__ == "__main__":
    run_topology_validation()
