#!/usr/bin/env python3
"""Stage a seeded random audit batch of the CGHD-annotation reference for human verification in
the existing net-GT UI (wire_detection/benchmark/gt_verify_ui.py, driven through
cghd_audit_ui.py so the committed GT files are never touched).

Sample: 40 images drawn with numpy default_rng(20260928) from the PRIMARY scoring set
(reference-clean, stem not among the 31 human-verified images).

Writes <out>/
  real_nets_working.json   same schema as ground_truth/real_nets_working.json (key <stem>_jpg,
                           nets [[idx,'e'],...], n_components, electrical_idxs,
                           components{idx:{type,cx,cy}}, img_wh, source="cghd-annotation-derived
                           ... pending human audit"); edited in place by the UI
  net_gt_ui_meta.json      {<stem>_jpg: {img_wh, bboxes{idx:[x1,y1,x2,y2] normalised]}}
  overlays/<stem>.png      grayscale CGHD photo, long side 1600 (derived from CGHD: CC licence,
                           gitignored, do not commit)
  sample.json              the sampled stems + seed + provenance

  PYTHONPATH=~/circuit-digitization python cghd_audit_export.py --ref out/cghd_ref_nets_v2.json --out out/cghd_ref_audit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import list_samples, load_gray, load_shapes, our_type_name  # noqa

SEED = 20260928
N = 40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--human", default=str(Path.home() / "circuit-digitization/ground_truth/real_nets_verified.json"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ref = json.load(open(args.ref))
    h31 = {k[:-4] for k in json.load(open(args.human))}
    pool = sorted(s for s in ref if not s.startswith("_") and ref[s]["clean"] and s not in h31)
    rng = np.random.default_rng(SEED)
    pick = sorted(rng.choice(pool, size=N, replace=False).tolist())
    out = Path(args.out); (out / "overlays").mkdir(parents=True, exist_ok=True)
    dmap = {s: d for d, s in list_samples()}
    work, meta = {}, {}
    for s in pick:
        r = ref[s]
        W, H = r["img_wh"]
        shapes, _, _ = load_shapes(dmap[s], s)
        bb = {}
        for i in r["electrical_idxs"]:
            p = shapes[i]["points"]
            bb[str(i)] = [round(float(p[:, 0].min()) / W, 4), round(float(p[:, 1].min()) / H, 4),
                          round(float(p[:, 0].max()) / W, 4), round(float(p[:, 1].max()) / H, 4)]
        work[f"{s}_jpg"] = {"nets": r["nets"], "n_components": r["n_components"],
                            "electrical_idxs": r["electrical_idxs"], "components": r["components"],
                            "img_wh": [W, H], "drafter": r["drafter"],
                            "source": "cghd-annotation-derived (cghd_ref.py v2), pending human audit"}
        g = load_gray(dmap[s], s)
        sc = 1600 / max(W, H)
        g = cv2.resize(g, (int(round(W * sc)), int(round(H * sc))), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / "overlays" / f"{s}.png"), g)
        meta[f"{s}_jpg"] = {"img_wh": [g.shape[1], g.shape[0]], "bboxes": bb}
    json.dump(work, open(out / "real_nets_working.json", "w"), indent=2)
    json.dump(meta, open(out / "net_gt_ui_meta.json", "w"), indent=1)
    json.dump({"seed": SEED, "n": N, "pool": "reference-clean, not among the 31 human-verified",
               "pool_size": len(pool), "stems": pick,
               "provenance": "Derived from CGHD v12 annotations (Zenodo 10056817) by cghd_ref.py v2"},
              open(out / "sample.json", "w"), indent=1)
    print(f"staged {len(pick)} of {len(pool)} -> {out}")


if __name__ == "__main__":
    main()
