#!/usr/bin/env python3
"""Build the canonical verified net-GT for scoring from the UI working file.

Includes an image iff: (a) source is human-verified, (b) not marked excluded, and (c) it
passes physical sanity — every electrical component appears in <= its terminal count of nets
and in >= 1 net (no isolated part, no impossible over-connection). Images failing sanity are
dropped and reported (they are edit-slips / bad labels, unsafe to score).

Usage: python -m wire_detection.benchmark.build_verified_gt \
           [in=ground_truth/real_nets_working.json] [out=ground_truth/real_nets_verified.json]
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

MAX_TERMINALS = {
    "resistor": 2, "capacitor-unpolarized": 2, "capacitor-polarized": 2,
    "capacitor-adjustable": 2, "inductor": 2, "inductor-ferrite": 2,
    "diode": 2, "diode-LED": 2, "diode-zener": 2, "diode-thyrector": 2,
    "voltage-DC": 2, "voltage-AC": 2, "voltage-battery": 2,
    "transistor-BJT": 3, "transistor-FET": 3,
    "opamp": 5, "opamp-schmitt": 5, "IC-voltage-reg": 3, "IC-NE555": 8, "IC": 16,
}


def sanity(entry):
    """Return list of problem strings (empty == clean)."""
    keep = set(entry["electrical_idxs"])
    comps = {int(i): m for i, m in entry["components"].items()}
    cnt = Counter()
    for net in entry["nets"]:
        for ci in {int(c) for c, _ in net if int(c) in keep}:
            cnt[ci] += 1
    probs = []
    for ci in keep:
        t = comps[ci]["type"]
        mx = MAX_TERMINALS.get(t, 3)
        ap = cnt.get(ci, 0)
        if ap > mx:
            probs.append(f"{t}{ci} in {ap} nets (max {mx})")
        if ap == 0:
            probs.append(f"{t}{ci} isolated")
    return probs


def main():
    args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    src = Path(args.get("in", "ground_truth/real_nets_working.json"))
    out = Path(args.get("out", "ground_truth/real_nets_verified.json"))
    d = json.loads(src.read_text())
    keep, dropped = {}, []
    for k, v in d.items():
        if "human-verified" not in v.get("source", ""):
            continue
        if v.get("excluded"):
            dropped.append((k, "excluded")); continue
        probs = sanity(v)
        if probs:
            dropped.append((k, "; ".join(probs))); continue
        e = {kk: vv for kk, vv in v.items() if kk != "_nets_original"}
        keep[k] = e
    out.write_text(json.dumps(keep, indent=2))
    print(f"verified GT: {len(keep)} images -> {out}")
    if dropped:
        print(f"dropped {len(dropped)}:")
        for k, why in dropped:
            print(f"  {k[:-4]}: {why}")


if __name__ == "__main__":
    main()
