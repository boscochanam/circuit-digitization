#!/usr/bin/env python3
"""Synthetic intra-image size-heterogeneity stress test (R2-6, Access-2026-33821).

Starts from the authored synthgt CATALOG (the circuits behind
docs/research/experiments/synthetic_leaderboard.json) and derives variants in which ONE
axis-aligned component is drawn m times larger or smaller than authored, in BOTH axes
(long axis size*m, short axis 30*m), with its centre fixed. Wires are re-routed
pin-to-pin by the stock synthesizer (_route_net), so the authored netlist is unchanged.
A variant is kept only if it is geometrically clean: the resized box does not touch
any other box (8px margin) and no wire passes through a box it does not terminate on.
The same placeholder error model (ERROR_LEVELS L0-L4, 8 seeds) and the same
component-pair F1 as the leaderboard are used.

  uv run python wire_detection/benchmark/revision2/synth_mixed_size.py \
      --out docs/research/experiments/revision2/synth_mixed_size.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from methods import METHODS, run_method  # noqa: E402
from wire_detection.synthgt.circuits import CATALOG  # noqa: E402
from wire_detection.synthgt.evaluate import _comp_pairs, _make_std_pins, _prf  # noqa: E402
from wire_detection.synthgt.synthesize import (  # noqa: E402
    ERROR_LEVELS, _route_net, build_components, inject_errors, intended_pairs, pin_positions)

MULTS = [0.5, 2.0, 3.0]
SEEDS = 8


def build_variant(spec, idx, m):
    """Return (spec', components, wires, pin_pos) with component idx scaled by m."""
    if idx is not None:
        c = spec.comps[idx]
        comps_new = list(spec.comps)
        comps_new[idx] = dataclasses.replace(c, size=int(round(c.size * m)))
        spec = dataclasses.replace(spec, comps=comps_new, name=f"{spec.name}#{idx}x{m:g}")
    comps = build_components(spec)
    if idx is not None:
        c = spec.comps[idx]
        short = int(round(30 * m))
        w, h = (c.size, short) if c.orient == "H" else (short, c.size)
        cls = comps[idx][0]
        comps[idx] = (cls, [], (c.cx - w // 2, c.cy - h // 2, c.cx + w // 2, c.cy + h // 2))
    pin_pos = pin_positions(comps, spec)
    wires = []
    for net in spec.nets:
        wires.extend(_route_net(net, pin_pos))
    return spec, comps, wires, pin_pos


def _boxes_touch(a, b, margin=8):
    return not (a[2] + margin < b[0] or b[2] + margin < a[0] or
                a[3] + margin < b[1] or b[3] + margin < a[1])


def _seg_hits_box(p, q, box, n=64):
    x1, y1, x2, y2 = box
    for k in range(1, n):
        t = k / n
        x, y = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
        if x1 < x < x2 and y1 < y < y2:
            return True
    return False


def is_clean(comps, wires, pin_pos, idx):
    box = comps[idx][2]
    if any(_boxes_touch(box, c[2]) for j, c in enumerate(comps) if j != idx):
        return False
    owner = {}
    for (ci, _pi), pt in pin_pos.items():
        owner.setdefault(pt, set()).add(ci)
    for p, q in wires:
        ends = owner.get(p, set()) | owner.get(q, set())
        for j, c in enumerate(comps):
            if j not in ends and _seg_hits_box(p, q, c[2]):
                return False
    return True


def sweep(spec, comps, wires, pin_pos, methods):
    gt = intended_pairs(spec)
    std = _make_std_pins(pin_pos, spec)
    out = {m: [] for m in methods}
    for sev in sorted(ERROR_LEVELS):
        n = 1 if sev == 0 else SEEDS
        acc = {m: 0.0 for m in methods}
        for seed in range(n):
            w = inject_errors(wires, sev, seed, pin_pos=pin_pos, components=comps)
            for m in methods:
                acc[m] += _prf(gt, _comp_pairs(run_method(m, w, comps, std, None)))[2]
        for m in methods:
            out[m].append(acc[m] / n)
    return out


def summarise(rows, methods):
    agg = {}
    for m in methods:
        by = [sum(r["f1"][m][s] for r in rows) / len(rows) for s in range(len(ERROR_LEVELS))]
        agg[m] = {"by_severity": by, "clean": by[0], "mean_err_f1": sum(by[1:]) / (len(by) - 1)}
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/research/experiments/revision2/synth_mixed_size.json")
    args = ap.parse_args()

    base_rows = []
    for spec in CATALOG:
        sp, comps, wires, pp = build_variant(spec, None, 1.0)
        base_rows.append({"circuit": spec.name, "f1": sweep(sp, comps, wires, pp, METHODS)})
    groups = {"authored (control)": base_rows}
    variants = {}
    for m in MULTS:
        rows, rejected = [], 0
        for spec in CATALOG:
            for idx, c in enumerate(spec.comps):
                if (c.angle or 0) or c.type == "gnd":
                    continue
                sp, comps, wires, pp = build_variant(spec, idx, m)
                if not is_clean(comps, wires, pp, idx):
                    rejected += 1
                    continue
                rows.append({"circuit": sp.name, "f1": sweep(sp, comps, wires, pp, METHODS)})
        groups[f"one component x{m:g}"] = rows
        variants[str(m)] = {"kept": len(rows), "rejected_geometry": rejected}
        print(f"x{m}: kept {len(rows)}, rejected {rejected}")

    summary = {g: {"n_variants": len(r), **{"methods": summarise(r, METHODS)}}
               for g, r in groups.items()}
    payload = {"experiment": "synthgt single-component size heterogeneity",
               "multipliers": MULTS, "seeds": SEEDS, "error_levels": ERROR_LEVELS,
               "methods": METHODS, "variant_counts": variants, "summary": summary,
               "rows": groups,
               "notes": ["F1 = mean component-pair F1 per (variant, seed), leaderboard convention",
                         "error model is the placeholder synthgt model in fixed pixels",
                         "control row with the full catalog reproduces synthetic_leaderboard.json "
                         "for registry strategies (seeds=8)"]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(payload, open(args.out, "w"), indent=1)
    print(f"\n{'group':<24}{'n':>4}  " + "".join(f"{m[:14]:>16}" for m in METHODS))
    for g, s in summary.items():
        print(f"{g:<24}{s['n_variants']:>4}  clean " +
              "".join(f"{s['methods'][m]['clean']:>16.3f}" for m in METHODS))
        print(f"{'':<24}{'':>4}  err   " +
              "".join(f"{s['methods'][m]['mean_err_f1']:>16.3f}" for m in METHODS))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
