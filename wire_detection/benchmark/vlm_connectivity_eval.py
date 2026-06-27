"""Claude-as-VLM circuit connectivity benchmark.

Tests whether a general vision-language model can recover circuit *connectivity* (the
join target of this paper) from an image, scored with the SAME component-pair F1 used for
the geometric join (synthgt.evaluate._prf / intended_pairs).

Two-phase, deliberately decoupled so the scoring is deterministic and the model responses
are an auditable artifact:

  Phase 1 (get responses):  a fresh, context-free Claude Code subagent is spawned per
    image with PROMPT below; it reads the image and returns JSON {"nets": [[label,...]]}.
    Each net lists the component LABELS that meet at one electrical node. Responses are
    saved to a responses JSON (one entry per circuit/image). This phase is driven by the
    Claude Code harness (see scripts/run_vlm_subagents.md) or, for external reproduction,
    by --api which calls the Anthropic API directly.

  Phase 2 (score):  this module reads the responses JSON, recomputes ground-truth pairs
    (synthetic: intended_pairs(spec); real: all-pairs within real_nets.json nets), and
    reports precision / recall / F1 per circuit and in aggregate.

Component label -> index mapping: the printed designator's integer N maps to component
index N-1 (R2 -> 1, V1 -> 0, R6 -> 5). For synthetic images render.py prints these; for
real images the overlay renderer prints the GT component index on each detected box, so the
model is given the detections (as the pipeline is) and tested ONLY on connectivity.
"""
from __future__ import annotations

import json
import re
from itertools import combinations

# Model used for the first-party numbers reported in the paper. Update if re-run.
VLM_MODEL_ID = "claude-opus-4-8 (via Claude Code subagent, no shared context)"

PROMPT = """You are reading a single electronic circuit schematic image.

Image path: {image_path}

Read the image. Every component is drawn as a box with a printed label (for example V1, R2,
R6, L3, D4, GND5). Your task is to recover the NETLIST connectivity: determine which
component terminals are electrically connected by the drawn wires.

An electrical "net" (node) is a set of component terminals that are all joined together by
wires, directly or through wire junctions/corners. Two terminals are on the same net only
if you can trace an unbroken wire path between them WITHOUT passing through a component body.

Output ONLY a JSON object, no prose, of this exact form:
{{"nets": [["V1", "R2"], ["R2", "R3", "R6"], ...]}}
- Each inner list is one electrical node: the component labels whose terminals meet there.
- A component appears in as many nets as it has connected terminals (usually 2).
- Use the EXACT printed labels from the image.
"""


def designator_to_index(label: str, zero_based: bool = False) -> int | None:
    """Synthetic labels encode index+1 ('R2'->1, 'V1'->0); real overlays print the raw
    component index ('7'->7) so pass zero_based=True. Returns None if no integer present."""
    m = re.search(r"(\d+)", label)
    if not m:
        return None
    n = int(m.group(1))
    return n if zero_based else n - 1


def pairs_from_vlm_nets(nets: list[list[str]], n_components: int | None = None,
                        zero_based: bool = False, keep: set[int] | None = None) -> set[tuple[int, int]]:
    """Map VLM label-nets to connected component-index pairs (same convention as
    synthesize.intended_pairs / evaluate._comp_pairs). `keep` restricts to electrical
    component indices when provided."""
    pairs: set[tuple[int, int]] = set()
    for net in nets:
        idxs = sorted({
            i for i in (designator_to_index(str(lbl), zero_based) for lbl in net)
            if i is not None and i >= 0
            and (n_components is None or i < n_components)
            and (keep is None or i in keep)
        })
        pairs.update(combinations(idxs, 2))
    return pairs


def pairs_from_gt_nets(nets: list[list], keep: set[int] | None = None) -> set[tuple[int, int]]:
    """All-pairs of component indices within each ground-truth net. `keep` restricts to
    electrical component indices when provided.

    Accepts nets as lists of (comp_idx, pin) tuples (real_nets.json / spec.nets)."""
    pairs: set[tuple[int, int]] = set()
    for net in nets:
        comps = sorted({int(ci) for ci, _pin in net if keep is None or int(ci) in keep})
        pairs.update(combinations(comps, 2))
    return pairs


def prf(gt: set, got: set) -> tuple[float, float, float]:
    """Precision/recall/F1 over component-pair sets (mirror of synthgt.evaluate._prf)."""
    if not gt and not got:
        return 1.0, 1.0, 1.0
    tp = len(gt & got)
    prec = tp / len(got) if got else (1.0 if not gt else 0.0)
    rec = tp / len(gt) if gt else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def parse_vlm_json(text: str) -> list[list[str]]:
    """Extract the {"nets": [...]} object from a model response (tolerant of code fences /
    surrounding prose). Returns [] if nothing parseable is found."""
    if not text:
        return []
    # strip code fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        # first balanced-looking object containing "nets"
        m = re.search(r"\{[^{}]*\"nets\".*\}", text, re.DOTALL)
        candidate = m.group(0) if m else text
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    nets = obj.get("nets", []) if isinstance(obj, dict) else []
    out = []
    for net in nets:
        if isinstance(net, list):
            out.append([str(x) for x in net])
    return out


# ---- scoring entry points -------------------------------------------------

def score_synthetic(responses: dict[str, str]) -> list[dict]:
    """responses: {circuit_name: raw_model_text}. Scores vs intended_pairs(spec)."""
    from wire_detection.synthgt.circuits import CATALOG_BY_NAME
    from wire_detection.synthgt.synthesize import intended_pairs

    rows = []
    for name, raw in responses.items():
        spec = CATALOG_BY_NAME.get(name)
        if spec is None:
            continue
        n = len(spec.comps)
        gt = intended_pairs(spec)
        pred = pairs_from_vlm_nets(parse_vlm_json(raw), n_components=n)
        p, r, f1 = prf(gt, pred)
        rows.append({"id": name, "comps": n, "precision": p, "recall": r, "f1": f1,
                     "n_gt_pairs": len(gt), "n_pred_pairs": len(pred)})
    return rows


def score_real(responses: dict[str, str], real_nets: dict[str, dict]) -> list[dict]:
    """responses: {image_id: raw_model_text}. real_nets: {image_id: {nets, n_components}}."""
    rows = []
    for img_id, raw in responses.items():
        gt_entry = real_nets.get(img_id)
        if gt_entry is None:
            continue
        n = int(gt_entry.get("n_components", 0))
        keep = set(gt_entry["electrical_idxs"]) if gt_entry.get("electrical_idxs") else None
        gt = pairs_from_gt_nets(gt_entry["nets"], keep=keep)
        pred = pairs_from_vlm_nets(parse_vlm_json(raw), n_components=n or None,
                                   zero_based=True, keep=keep)
        p, r, f1 = prf(gt, pred)
        rows.append({"id": img_id, "comps": n, "precision": p, "recall": r, "f1": f1,
                     "n_gt_pairs": len(gt), "n_pred_pairs": len(pred)})
    return rows


PROMPT_E2E = """You are reading a photographed hand-drawn electronic circuit schematic.

Image path: {image_path}

There are NO labels or boxes on the components --- you must find them yourself. Identify
every circuit component (resistor, capacitor, inductor, diode, transistor, voltage/current
source, IC/op-amp). Then trace the hand-drawn wires and determine the netlist: which
component terminals are electrically connected.

Output ONLY a JSON object, no prose:
{{"components": [{{"id": "R1", "type": "resistor", "cx": 0.22, "cy": 0.51}}, ...],
  "nets": [["R1", "C1"], ["R1", "V1"], ...]}}
- components: every component you find. cx,cy = its center as a FRACTION of image width and
  height (0..1, top-left origin). Give it a short id (R1, C1, V1, L1, D1, ...).
- nets: each inner list is one electrical node --- the ids of components whose terminals
  meet there. A component appears in as many nets as it has connected terminals (usually 2).
"""


def _parse_e2e(text: str) -> tuple[list[dict], list[list[str]]]:
    """Parse the end-to-end response {"components":[...], "nets":[...]}."""
    if not text:
        return [], []
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        m = re.search(r"\{.*\"nets\".*\}", text, re.DOTALL)
        candidate = m.group(0) if m else text
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return [], []
    comps = obj.get("components", []) if isinstance(obj, dict) else []
    nets = [[str(x) for x in net] for net in obj.get("nets", []) if isinstance(net, list)]
    return comps, nets


def _match_components(vlm_comps: list[dict], gt_comps: dict, max_dist: float = 0.12) -> dict:
    """Greedy nearest-center assignment of VLM components -> GT electrical indices.

    gt_comps: {idx_str: {type, cx, cy}}. Returns {vlm_id: gt_idx} for matches within
    max_dist (normalized). Unmatched VLM components are dropped; unmatched GT components
    simply never appear in the predicted pairs (counted as missed connections)."""
    import math

    gt_items = [(int(k), v) for k, v in gt_comps.items()]
    pairs = []  # (dist, vlm_id, gt_idx)
    for vc in vlm_comps:
        vid = str(vc.get("id", ""))
        try:
            vx, vy = float(vc.get("cx")), float(vc.get("cy"))
        except (TypeError, ValueError):
            continue
        for gi, gv in gt_items:
            d = math.hypot(vx - gv["cx"], vy - gv["cy"])
            if d <= max_dist:
                pairs.append((d, vid, gi))
    pairs.sort(key=lambda p: p[0])
    mapping, used_v, used_g = {}, set(), set()
    for d, vid, gi in pairs:
        if vid in used_v or gi in used_g:
            continue
        mapping[vid] = gi
        used_v.add(vid)
        used_g.add(gi)
    return mapping


def score_real_e2e(responses: dict[str, str], real_nets: dict[str, dict]) -> list[dict]:
    """End-to-end scoring: VLM finds components from the raw scan, we match to GT by center,
    then score connectivity F1 on GT electrical pairs."""
    rows = []
    for img_id, raw in responses.items():
        gt_entry = real_nets.get(img_id)
        if gt_entry is None or "components" not in gt_entry:
            continue
        keep = set(gt_entry["electrical_idxs"])
        gt = pairs_from_gt_nets(gt_entry["nets"], keep=keep)
        vlm_comps, vlm_nets = _parse_e2e(raw)
        mapping = _match_components(vlm_comps, gt_entry["components"])
        # map VLM nets (by vlm id) -> GT index pairs
        pred = set()
        for net in vlm_nets:
            idxs = sorted({mapping[v] for v in net if v in mapping})
            pred.update(combinations(idxs, 2))
        p, r, f1 = prf(gt, pred)
        rows.append({"id": img_id, "comps": len(keep), "precision": p, "recall": r, "f1": f1,
                     "n_gt_pairs": len(gt), "n_pred_pairs": len(pred),
                     "matched": len(mapping), "vlm_found": len(vlm_comps)})
    return rows


def _print_table(rows: list[dict], title: str) -> None:
    if not rows:
        print(f"{title}: no rows")
        return
    print(f"\n{title}")
    print(f"{'circuit':<18}{'comps':>6}{'prec':>8}{'rec':>8}{'f1':>8}")
    print("-" * 48)
    for row in rows:
        print(f"{row['id']:<18}{row['comps']:>6}{row['precision']:>8.2f}"
              f"{row['recall']:>8.2f}{row['f1']:>8.2f}")
    n = len(rows)
    mp = sum(r["precision"] for r in rows) / n
    mr = sum(r["recall"] for r in rows) / n
    mf = sum(r["f1"] for r in rows) / n
    omitted = sum(max(0, r["n_gt_pairs"] - round(r["recall"] * r["n_gt_pairs"]))
                  for r in rows)
    tot_gt = sum(r["n_gt_pairs"] for r in rows)
    print("-" * 48)
    print(f"{'MEAN':<18}{'':>6}{mp:>8.2f}{mr:>8.2f}{mf:>8.2f}")
    if tot_gt:
        print(f"connections omitted: {omitted}/{tot_gt} ({100 * omitted / tot_gt:.0f}% of GT pairs)")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Score Claude-as-VLM connectivity responses.")
    ap.add_argument("responses", help="JSON {id: raw_model_text}")
    ap.add_argument("--real", help="real_nets.json for real-image scoring (else synthetic)")
    ap.add_argument("--e2e", action="store_true",
                    help="end-to-end scoring (VLM found components from raw scan; match by center)")
    ap.add_argument("--out", help="write per-circuit results JSON here")
    args = ap.parse_args()

    with open(args.responses) as f:
        responses = json.load(f)

    if args.real:
        with open(args.real) as f:
            real_nets = json.load(f)
        if args.e2e:
            rows = score_real_e2e(responses, real_nets)
            _print_table(rows, "Claude-VLM connectivity on REAL images (end-to-end, raw scan)")
        else:
            rows = score_real(responses, real_nets)
            _print_table(rows, "Claude-VLM connectivity on REAL images (given detections)")
    else:
        rows = score_synthetic(responses)
        _print_table(rows, "Claude-VLM connectivity on SYNTHETIC circuits")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(rows, f, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
