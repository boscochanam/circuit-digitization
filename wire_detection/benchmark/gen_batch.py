#!/usr/bin/env python3
"""Generate a complexity-spread batch of NEW net-GT proposals (excluding the first 10) for
human verification: proposal nets (graph_scale on perfect wires), clean wires-only overlay,
and electrical-component bboxes. Outputs batch2_nets.json + clean2/*.png + clean2/meta.json."""
from __future__ import annotations
import json
from pathlib import Path
import cv2

from wire_detection.core.component_classes import COMPONENT_TYPES, PREFIX_MAP, SIMULATABLE_PREFIXES
from wire_detection.core.join_strategies import make_pins, make_pins_junction_aware, run_strategy
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, GT_WIRE_LABELS, find_hdc_label, parse_components, parse_gt_wires,
    electrical_indices, netlist_to_nets, discover, GT_STRATEGY,
)

DONE = {"C84_D2_P1", "C22_D2_P3", "C29_D2_P4", "C15_D2_P2", "C20_D2_P2",
        "C138_D1_P3", "C92_D1_P3", "C109_D2_P3", "C21_D1_P3", "C28_D1_P3"}
N_NEW = 25

# structural / measurement annotations that aren't circuit elements (fine to ignore)
STRUCTURAL = {"junction", "terminal", "gnd", "crossover", "wire", "text", "vss", "vdd",
              "probe", "probe-current", "probe-voltage", "antenna", "__background__"}


def get_comps(name):
    img = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    if img is None or hdc is None:
        return None
    h, w = img.shape
    return parse_components(hdc.read_text(), w, h)


def comp_count(name):
    comps = get_comps(name)
    return len(electrical_indices(comps)) if comps else None


def is_clean(name):
    """Exclude circuits containing any UNSUPPORTED real device (triac/fuse/switch/relay/
    transformer/varistor/gate/pot/...). Such parts get filtered from the SPICE-active set,
    leaving an unrepresentative net-GT, so the whole circuit is dropped from the benchmark."""
    comps = get_comps(name)
    if not comps:
        return False
    for cls, _v, _b in comps:
        t = COMPONENT_TYPES.get(int(cls), "unknown")
        if t in STRUCTURAL:
            continue
        if PREFIX_MAP.get(t) in SIMULATABLE_PREFIXES:
            continue
        return False  # an unsupported real device -> exclude this circuit
    return True


def pick():
    rem = [n for n in discover() if n not in DONE]
    counts = {n: comp_count(n) for n in rem}
    counts = {n: c for n, c in counts.items() if c and c >= 2 and is_clean(n)}  # >=2 elec, no unsupported devices
    print(f"clean candidate pool (all real parts SPICE-active, >=2 elec): {len(counts)}")
    ranked = sorted(counts, key=lambda k: counts[k])
    if len(ranked) <= N_NEW:
        return ranked
    step = len(ranked) / N_NEW
    return [ranked[int(i * step)] for i in range(N_NEW)]


def build(name, outdir):
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    wf = GT_WIRE_LABELS / f"{name}_jpg.txt"
    if gray is None or hdc is None or not wf.exists():
        return None, None
    h, w = gray.shape
    comps = parse_components(hdc.read_text(), w, h)
    wires = parse_gt_wires(wf.read_text(), w, h)
    if not comps or not wires:
        return None, None
    std = make_pins(wires, comps); junc = make_pins_junction_aware(wires, comps)
    _p, nl = run_strategy(GT_STRATEGY, wires, comps, std_pins=std, junc_pins=junc)
    nets = netlist_to_nets(nl)
    elec = electrical_indices(comps)
    cmeta = {}
    for i in elec:
        x1, y1, x2, y2 = comps[i][2]
        cmeta[i] = {"type": COMPONENT_TYPES.get(int(comps[i][0]), "unknown"),
                    "cx": round((x1 + x2) / 2 / w, 4), "cy": round((y1 + y2) / 2 / h, 4)}
    entry = {"nets": nets, "n_components": len(comps), "electrical_idxs": elec,
             "components": cmeta, "img_wh": [w, h], "n_wires": len(wires),
             "source": f"perfect-GT-wires + {GT_STRATEGY} (proposal, pending human verify)"}
    # clean overlay (wires only) + bbox meta
    scale = max(1, int(round(1500 / max(w, h))))
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if scale > 1:
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    S = lambda p: (int(p[0] * scale), int(p[1] * scale))
    for a, b in wires:
        cv2.line(img, S(a), S(b), (40, 40, 40), max(2, scale))
    outdir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(outdir / f"{name}.png"), img)
    meta = {"img_wh": [img.shape[1], img.shape[0]],
            "bboxes": {str(i): [round(comps[i][2][0]/w, 4), round(comps[i][2][1]/h, 4),
                                round(comps[i][2][2]/w, 4), round(comps[i][2][3]/h, 4)] for i in elec}}
    return entry, meta


def main():
    names = pick()
    print(f"selected {len(names)} new images (elec-comp spread)")
    outdir = Path("output/net_gt_clean2")
    nets_out, meta_out = {}, {}
    for n in names:
        e, m = build(n, outdir)
        if e is None:
            print("  skip", n); continue
        nets_out[f"{n}_jpg"] = e; meta_out[f"{n}_jpg"] = m
        print(f"  {n}: {len(e['electrical_idxs'])} elec, {len([x for x in e['nets'] if len({c for c,_ in x})>1])} multi-nets")
    Path("ground_truth/real_nets_batch2.json").write_text(json.dumps(nets_out, indent=2))
    (outdir / "meta.json").write_text(json.dumps(meta_out))
    print(f"\nwrote ground_truth/real_nets_batch2.json ({len(nets_out)}) + {outdir}/meta.json")


if __name__ == "__main__":
    main()
