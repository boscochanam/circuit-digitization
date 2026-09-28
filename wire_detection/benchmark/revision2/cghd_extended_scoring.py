#!/usr/bin/env python3
"""Extended-scoring variants of the CGHD-annotation held-out connectivity benchmark (revision 2).

Same frozen photo-input predictions and the same reference (v2) as the primary table; only the
SCORING changes. Pin-level predicted nets over all components come from cghd_eval_ext.py
(cghd_ref/cghd_eval_ext_photo.json), because the stored cghd_eval_photo.json only keeps pairs over
the electrical subset.

Variants (both applied identically to reference and predictions):
  primary        scored set = electrical subset (SIMULATABLE_PREFIXES); must reproduce
                 cghd_ref_benchmark.json exactly (ours 0.711 on the 164 held-out clean images).
  A_extended     scored set = electrical + EXT_TYPES (switch, potentiometer/adjustable resistor,
                 photoresistor, fuse, lamp, varistor, crystal, speaker, microphone).
  A_core         sensitivity: electrical + switch + resistor-adjustable + resistor-photo only.
  C_grounds_merged  all nets touching any CGHD 'gnd' symbol are one node; separately all nets
                 touching any 'vss' symbol (and 'vdd', absent in CGHD) are one node; in the reference
                 AND in every prediction (predicted nodes holding a gnd/vss pin). Scored set = electrical.
  ABC_combined   extended scored set + switches closed + grounds merged.
  B_switch_closed  every switch is a wire: in the reference, all nets containing a given switch are
                 unioned (transitively); in each prediction, all predicted nodes holding any pin of
                 a switch are unioned. Switches are not scored; scored set = electrical subset.
Also re-derived: the previously reported switch-closed number (stored predictions, NOT merged, vs
the rebuilt reference cghd_ref_nets_v2_switch_closed.json on its own held-out clean set), and the
symmetric merge against that rebuilt reference on the 164.

Subsets: heldout_clean (164; primary) and heldout_clean_not_wire134 (139; drops the images whose
stem is in the 134-image wire benchmark, ground_truth/wire_labels/). The drawing-level exclusion
(any picture of a drawing in the 134 set; 123 images) is reported as well.

  .venv/bin/python -m wire_detection.benchmark.revision2.cghd_extended_scoring
"""
from __future__ import annotations

import json
import os
import re
from itertools import combinations
from pathlib import Path

import numpy as np

from wire_detection.benchmark.revision2.cghd_common import our_type_name
from wire_detection.benchmark.revision2.stats_strata import (
    SEED_BOOT, SEED_PERM, holm, micro_scalar, paired_bootstrap, per_image_prf, perm_test, stratum_summary)

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "docs/research/experiments/revision2"
RAW = EXP / "cghd_ref"
REF = REPO / "ground_truth/cghd_ref/cghd_ref_nets.json"
OUT_JSON = EXP / "cghd_ref_extended_scoring.json"
OURS = "scale_completion"
BASELINES = ["degree_budget", "graph_scale", "graph_rescue", "production",
             "hough_link44_reach48", "cc_detCCL_d15"]
METHODS = [OURS] + BASELINES
SWITCH = "switch"
CORE_EXT = {"switch", "resistor-adjustable", "resistor-photo"}
EXT_TYPES = CORE_EXT | {"fuse", "lamp", "varistor", "crystal", "speaker", "microphone"}


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def pairs_of(groups, keep):
    out = set()
    for g in groups:
        out.update(combinations(sorted({c for c in g if c in keep}), 2))
    return out


def merge_through(groups, key_of):
    """Union every group containing a component c with key_of[c] (transitively, per key);
    drop nothing. key_of maps component idx -> merge key (switch: its own idx; all gnd: 'GND';
    all vss: 'VSS')."""
    uf = UF()
    for gi, g in enumerate(groups):
        uf.find(gi)
        for c in g:
            if c in key_of:
                uf.union(gi, ("K", key_of[c]))
    merged = {}
    for gi, g in enumerate(groups):
        merged.setdefault(uf.find(gi), set()).update(g)
    return list(merged.values())


def close_switches(groups, switch_idxs):
    return merge_through(groups, {c: ("S", c) for c in switch_idxs})


GROUND_KEYS = {"gnd": "GND", "vss": "VSS", "vdd": "VDD"}   # CGHD labels; 'vdd' does not occur


def ref_groups(ref_img):
    return [{int(c) for c, _ in net} for net in ref_img["nets"]]


def pred_groups(meth_rec):
    return [{int(c) for c, _ in node} for node in meth_rec["nodes"]]


def counts(gt, pred):
    return [len(gt & pred), len(pred - gt), len(gt - pred)]


VARIANT_OPS = {"primary": set(), "A_extended": {"ext"}, "A_core": {"core"},
               "B_switch_closed": {"switch"}, "C_grounds_merged": {"ground"},
               "ABC_combined": {"ext", "switch", "ground"}}
VARIANTS = ["A_extended", "A_core", "B_switch_closed", "C_grounds_merged", "ABC_combined"]


def score_variant(X, ref, stems, variant):
    """-> {method: (n,3) counts}, per-image ref pair sets."""
    C = {m: [] for m in METHODS}
    refp = []
    for s in stems:
        r, x = ref[s], X["images"][s]
        types = [our_type_name(l) for l in x["labels"]]
        elec = set(r["electrical_idxs"])
        ops = VARIANT_OPS[variant]
        keep = set(elec)
        if "ext" in ops:
            keep |= {i for i, t in enumerate(types) if t in EXT_TYPES}
        if "core" in ops:
            keep |= {i for i, t in enumerate(types) if t in CORE_EXT}
        key_of = {}
        if "switch" in ops:
            key_of.update({i: ("S", i) for i, t in enumerate(types) if t == SWITCH})
        if "ground" in ops:
            key_of.update({i: GROUND_KEYS[l] for i, l in enumerate(x["labels"]) if l in GROUND_KEYS})
        rg = ref_groups(r)
        if key_of:
            rg = merge_through(rg, key_of)
        gt = pairs_of(rg, keep)
        refp.append(gt)
        for m in METHODS:
            pg = pred_groups(x["methods"][m])
            if key_of:
                pg = merge_through(pg, key_of)
            C[m].append(counts(gt, pairs_of(pg, keep)))
    return {m: np.array(v) for m, v in C.items()}, refp


def analyse(C, n_ref_pairs):
    res = {"n_images": int(len(C[OURS])), "n_ref_pairs": int(n_ref_pairs), "methods": {}, "tests": {}}
    idx = np.arange(len(C[OURS]))
    for m in METHODS:
        res["methods"][m] = stratum_summary(C[m], idx, np.random.default_rng(SEED_BOOT))
    fo = per_image_prf(C[OURS])[:, 2]
    for m in BASELINES:
        d = fo - per_image_prf(C[m])[:, 2]
        res["tests"][m] = {"bootstrap_micro": paired_bootstrap(C[OURS], C[m], np.random.default_rng(SEED_BOOT)),
                           "permutation": perm_test(C[OURS], C[m], np.random.default_rng(SEED_PERM)),
                           "win_tie_loss_f1": [int((d > 1e-12).sum()), int((np.abs(d) <= 1e-12).sum()),
                                               int((d < -1e-12).sum())]}
    hb = holm([res["tests"][m]["bootstrap_micro"]["p_two_sided"] for m in BASELINES])
    hp = holm([res["tests"][m]["permutation"]["p_micro_f1"] for m in BASELINES])
    for m, a, b in zip(BASELINES, hb, hp):
        res["tests"][m]["holm"] = {"bootstrap_micro": a, "perm_micro": b, "reported_max": max(a, b)}
    return res


def change_summary(Cv, Cp, refv, refp):
    ch_img = [int(not np.array_equal(Cv[m][i], Cp[m][i])) for m in [OURS] for i in range(len(refv))]
    added = sum(len(a - b) for a, b in zip(refv, refp))
    removed = sum(len(b - a) for a, b in zip(refv, refp))
    return {"n_images_ref_pairs_changed": int(sum(a != b for a, b in zip(refv, refp))),
            "ref_pairs_added": int(added), "ref_pairs_removed": int(removed),
            "ref_pairs_primary": int(sum(len(b) for b in refp)), "ref_pairs_variant": int(sum(len(a) for a in refv)),
            "n_images_ours_counts_changed": int(sum(ch_img)),
            "per_method_images_counts_changed": {m: int(sum(not np.array_equal(Cv[m][i], Cp[m][i])
                                                            for i in range(len(refv)))) for m in METHODS}}


def drawing(stem):
    return re.match(r"(C\d+_D\d+)_P\d+", stem).group(1)


def main():
    ref = json.load(open(REF))
    X = json.load(open(RAW / "cghd_eval_ext_photo.json"))
    E = json.load(open(RAW / "cghd_eval_photo.json"))
    prim = json.load(open(EXP / "cghd_ref_benchmark.json"))["conditions"]["photo"]["subsets"]["heldout_clean"]
    human = json.load(open(REPO / "ground_truth/real_nets_verified.json"))
    h31 = {k[:-4] for k in human}
    stems_all = sorted(k for k in ref if not k.startswith("_"))
    ho = [s for s in stems_all if ref[s]["clean"] and s not in h31]
    assert sorted(X["images"]) == ho, "ext eval must cover exactly the 164 held-out clean images"
    wl = {f[:-len("_jpg.txt")] for f in os.listdir(REPO / "ground_truth/wire_labels") if f.endswith("_jpg.txt")}
    wd = {drawing(s) for s in wl}
    subsets = {"heldout_clean": ho,
               "heldout_clean_not_wire134": [s for s in ho if s not in wl],
               "heldout_clean_not_wire134_drawing": [s for s in ho if drawing(s) not in wd]}

    # ---------------- reproduction check (primary scoring through this code path)
    repro = {"stored_pairs_identical": True, "counts_identical_to_cghd_eval_photo": True, "mismatches": []}
    Cp, _ = score_variant(X, ref, ho, "primary")
    for i, s in enumerate(ho):
        for m in METHODS:
            st = E["images"][s]
            new_pairs = sorted(map(list, pairs_of(pred_groups(X["images"][s]["methods"][m]), set(ref[s]["electrical_idxs"]))))
            if new_pairs != X["images"][s]["methods"][m]["pairs_elec"] or new_pairs != st["pred_pairs"][m]:
                repro["stored_pairs_identical"] = False; repro["mismatches"].append([s, m, "pairs"])
            if list(Cp[m][i]) != st["methods"][m]:
                repro["counts_identical_to_cghd_eval_photo"] = False; repro["mismatches"].append([s, m, "counts"])
    repro["micro_f1_this_path"] = {m: micro_scalar(Cp[m])[2] for m in METHODS}
    repro["micro_f1_cghd_ref_benchmark_json"] = {m: prim["methods"][m]["micro_f1"] for m in METHODS}
    repro["exact"] = all(abs(repro["micro_f1_this_path"][m] - repro["micro_f1_cghd_ref_benchmark_json"][m]) < 1e-12
                         for m in METHODS) and repro["stored_pairs_identical"] and repro["counts_identical_to_cghd_eval_photo"]

    # ---------------- extended type inventory on the 164
    inv = {}
    for s in ho:
        for l in X["images"][s]["labels"]:
            t = our_type_name(l)
            if t in EXT_TYPES:
                inv.setdefault(t, {"cghd_label": l, "instances": 0, "images": set()})
                inv[t]["instances"] += 1; inv[t]["images"].add(s)
    inventory = {t: {"cghd_label": v["cghd_label"], "instances": v["instances"], "images": len(v["images"])}
                 for t, v in sorted(inv.items())}
    ext_imgs = sum(any(our_type_name(l) in EXT_TYPES for l in X["images"][s]["labels"]) for s in ho)
    sw_imgs = sum(any(our_type_name(l) == SWITCH for l in X["images"][s]["labels"]) for s in ho)
    # reference health of the added parts: isolated / in more nets than 2 (3 for pots)
    iso, over = [], []
    for s in ho:
        cnt = {}
        for g in ref_groups(ref[s]):
            for c in g:
                cnt[c] = cnt.get(c, 0) + 1
        for i, l in enumerate(X["images"][s]["labels"]):
            t = our_type_name(l)
            if t in EXT_TYPES:
                if cnt.get(i, 0) == 0:
                    iso.append([s, i, t])
                elif cnt[i] > (3 if t == "resistor-adjustable" else 2):
                    over.append([s, i, t, cnt[i]])

    # ground inventory on the 164
    gi = {"n_images_ge2_gnd": 0, "n_images_ge2_vss": 0, "n_images_ge2_gnd_or_vss": 0,
          "n_images_any_gnd": 0, "n_images_any_vss": 0, "n_images_gnd_and_vss": 0, "n_vdd": 0}
    for s in ho:
        labs = X["images"][s]["labels"]
        ng, nv = labs.count("gnd"), labs.count("vss")
        gi["n_images_ge2_gnd"] += ng >= 2; gi["n_images_ge2_vss"] += nv >= 2
        gi["n_images_ge2_gnd_or_vss"] += (ng >= 2 or nv >= 2)
        gi["n_images_any_gnd"] += ng > 0; gi["n_images_any_vss"] += nv > 0
        gi["n_images_gnd_and_vss"] += (ng > 0 and nv > 0); gi["n_vdd"] += labs.count("vdd")
    gi = {k: int(v) for k, v in gi.items()}

    out = {"reference": str(REF.relative_to(REPO)), "predictions": "cghd_ref/cghd_eval_ext_photo.json "
           "(cghd_eval_ext.py; frozen photo-input path of cghd_eval.py, pin-level nets over all components)",
           "input": "photo, long side 1024", "subset_sizes": {k: len(v) for k, v in subsets.items()},
           "ext_types": sorted(EXT_TYPES), "core_ext_types": sorted(CORE_EXT),
           "ext_type_inventory_heldout164": inventory, "n_images_with_ext_types": int(ext_imgs),
           "n_images_with_switch": int(sw_imgs), "ground_inventory_heldout164": gi,
           "reference_health_of_added_parts": {"isolated": iso, "overconnected": over},
           "reproduction_check": repro, "variants": {}}

    for sub, stems in subsets.items():
        Cprim, rprim = score_variant(X, ref, stems, "primary")
        block = {"primary": analyse(Cprim, sum(len(p) for p in rprim))}
        for v in VARIANTS:
            Cv, rv = score_variant(X, ref, stems, v)
            block[v] = analyse(Cv, sum(len(p) for p in rv))
            block[v]["change_vs_primary"] = change_summary(Cv, Cprim, rv, rprim)
        out["variants"][sub] = block

    # ---------------- previously reported switch-closed number + symmetric version on the rebuilt ref
    rv = json.load(open(RAW / "cghd_ref_nets_v2_switch_closed.json"))
    idx_prev = [s for s in stems_all if rv[s]["clean"] and s not in h31]
    prev = {}
    for m in METHODS:
        C = []
        for s in idx_prev:
            keep = set(rv[s]["electrical_idxs"])
            gt = pairs_of(ref_groups(rv[s]), keep)
            pred = {tuple(p) for p in E["images"][s]["pred_pairs"][m]}
            C.append(counts(gt, pred))
        prev[m] = micro_scalar(np.array(C))[2]
    sym_rebuilt, asym_rebuilt, agree = {m: [] for m in METHODS}, {m: [] for m in METHODS}, [0, 0, 0]
    for s in ho:
        keep = set(ref[s]["electrical_idxs"])
        sw = {i for i, l in enumerate(X["images"][s]["labels"]) if our_type_name(l) == SWITCH}
        gt_rb = pairs_of(ref_groups(rv[s]), keep)
        gt_mine = pairs_of(close_switches(ref_groups(ref[s]), sw), keep)
        agree[0] += len(gt_rb & gt_mine); agree[1] += len(gt_mine - gt_rb); agree[2] += len(gt_rb - gt_mine)
        for m in METHODS:
            pg = pred_groups(X["images"][s]["methods"][m])
            sym_rebuilt[m].append(counts(gt_rb, pairs_of(close_switches(pg, sw), keep)))
            asym_rebuilt[m].append(counts(gt_rb, pairs_of(pg, keep)))
    out["switch_closed_previous_vs_symmetric"] = {
        "previous_reported": {"description": "stored predictions NOT merged across switches vs rebuilt "
                              "cghd_ref_nets_v2_switch_closed.json, its own held-out clean set",
                              "n_images": len(idx_prev), "micro_f1": prev},
        "rebuilt_ref_on_164_asymmetric": {m: micro_scalar(np.array(v))[2] for m, v in asym_rebuilt.items()},
        "rebuilt_ref_on_164_symmetric": {m: micro_scalar(np.array(v))[2] for m, v in sym_rebuilt.items()},
        "ref_pairs_mine_vs_rebuilt_on_164": {"both": agree[0], "only_net_union": agree[1], "only_rebuilt": agree[2]},
    }
    json.dump(out, open(OUT_JSON, "w"), indent=1, default=list)

    # console
    print("repro exact:", repro["exact"], {m: round(v, 4) for m, v in repro["micro_f1_this_path"].items()})
    print("inventory", inventory, "ext imgs", ext_imgs, "switch imgs", sw_imgs, "iso", len(iso), "over", len(over))
    for sub in subsets:
        for v in ["primary"] + VARIANTS:
            r = out["variants"][sub][v]
            print(f"\n[{sub}] {v}: n={r['n_images']} pairs={r['n_ref_pairs']} {r.get('change_vs_primary', '')}")
            for m in METHODS:
                q = r["methods"][m]; t = r["tests"].get(m)
                extra = "" if t is None else (f" d={t['bootstrap_micro']['diff']:+.3f} [{t['bootstrap_micro']['ci95'][0]:+.3f},"
                                              f"{t['bootstrap_micro']['ci95'][1]:+.3f}] pH={t['holm']['reported_max']:.4f} "
                                              f"wtl={t['win_tie_loss_f1']}")
                print(f"  {m:<22} F1={q['micro_f1']:.3f} [{q['micro_f1_ci95'][0]:.3f},{q['micro_f1_ci95'][1]:.3f}] "
                      f"P={q['micro_p']:.3f} R={q['micro_r']:.3f} mac={q['macro_f1']:.3f} "
                      f"{q['tp']}/{q['fp']}/{q['fn']}{extra}")
    print(json.dumps(out["switch_closed_previous_vs_symmetric"], indent=0))
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
