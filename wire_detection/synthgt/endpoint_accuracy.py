"""Endpoint-to-component accuracy: for each wire endpoint, did the join
assign it to the correct component?

Ground truth: from synthesize_clean, each wire connects two pins, each pin
belongs to a specific component. So for each endpoint, the GT component is known.

After join: find the nearest derived pin for each endpoint. If within join
radius, assign endpoint to that component. Compare vs GT.
"""
from __future__ import annotations
import math
from wire_detection.synthgt.synthesize import (
    inject_errors, synthesize_clean, pin_positions,
)
from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.core.join_strategies import make_pins

JOIN_RADIUS = 30  # px — must match the join algorithm's radius


def endpoint_component_accuracy(spec, severity, seed):
    """Return (accuracy, n_endpoints, n_correct, details).
    
    details: list of (endpoint, gt_comp, assigned_comp, dist_to_nearest_pin, correct)
    """
    components, wires_clean, gt_pins = synthesize_clean(spec)
    
    # Ground truth: for each wire, which components do its endpoints belong to?
    gt_endpoint_comp = []  # list of (endpoint, gt_component_idx)
    for w in wires_clean:
        for ep in [w[0], w[1]]:
            # Find which GT pin this endpoint is on (dist < 1px)
            best_dist = float('inf')
            best_comp = None
            for (ci, pi), (px, py) in gt_pins.items():
                d = math.hypot(ep[0] - px, ep[1] - py)
                if d < best_dist:
                    best_dist = d
                    best_comp = ci
            gt_endpoint_comp.append((ep, best_comp))
    
    # Inject errors
    if severity == 0:
        wires_err = list(wires_clean)
    else:
        wires_err = inject_errors(wires_clean, severity, seed,
                                  pin_pos=gt_pins, components=components)
    
    # Derived pins (what the join algorithm uses)
    derived = make_pins([], components)
    
    # For each error-injected endpoint, find nearest derived pin
    assigned = []
    for w in wires_err:
        for ep in [w[0], w[1]]:
            best_dist = float('inf')
            best_comp = None
            for p in derived:
                d = math.hypot(ep[0] - p.x, ep[1] - p.y)
                if d < best_dist:
                    best_dist = d
                    best_comp = p.component_idx
            assigned.append((ep, best_comp, best_dist))
    
    # Compare
    details = []
    n_correct = 0
    for (gt_ep, gt_comp), (as_ep, as_comp, dist) in zip(gt_endpoint_comp, assigned):
        correct = (gt_comp == as_comp)
        if correct:
            n_correct += 1
        details.append((gt_ep, gt_comp, as_comp, dist, correct))
    
    accuracy = n_correct / len(gt_endpoint_comp) if gt_endpoint_comp else 1.0
    return accuracy, len(gt_endpoint_comp), n_correct, details


def main():
    print("Endpoint-to-Component Accuracy")
    print("=" * 70)
    print(f"{'circuit':20s} {'L0':>6} {'L1':>6} {'L2':>6} {'L3':>6} {'L4':>6} {'mean':>6}")
    print("-" * 70)
    
    for spec in CATALOG:
        accs = []
        row = f"{spec.name:20s}"
        for sev in range(5):
            # Average over 8 seeds
            accs_seeds = []
            for seed in range(8):
                acc, _, _, _ = endpoint_component_accuracy(spec, sev, seed)
                accs_seeds.append(acc)
            mean_acc = sum(accs_seeds) / len(accs_seeds)
            accs.append(mean_acc)
            row += f" {mean_acc:.2f}"
        mean_all = sum(accs[1:]) / len(accs[1:])  # mean over L1-L4
        row += f" {mean_all:.2f}"
        print(row)
    
    print("-" * 70)
    print("accuracy = % of wire endpoints assigned to correct component")
    print(f"join radius = {JOIN_RADIUS}px")


if __name__ == "__main__":
    main()
