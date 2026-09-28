#!/usr/bin/env python3
"""Serve the existing net-GT verification UI on the CGHD-reference audit batch.

Reuses wire_detection/benchmark/gt_verify_ui.py unchanged; only its module-level paths are
redirected to ground_truth/cghd_ref_audit/ (so ground_truth/real_nets_working.json is never
edited) and the part-label table is extended to every electrical type in the batch.

  python -m wire_detection.benchmark.revision2.cghd_audit_ui [port]      # default 8766
Verified entries get source "human-verified (UI)" in ground_truth/cghd_ref_audit/real_nets_working.json;
the original reference nets are kept under "_nets_original" by the UI's save().
"""
from __future__ import annotations

import json
import sys
import time
from http.server import ThreadingHTTPServer

from wire_detection.benchmark import gt_verify_ui as ui

AUDIT = ui.ROOT / "ground_truth" / "cghd_ref_audit"
ui.GT = AUDIT / "real_nets_working.json"
ui.CLEAN = AUDIT / "overlays"
ui.META = json.loads((AUDIT / "net_gt_ui_meta.json").read_text())
ui.FLAGS = {}
ui.TYPE_ABBR = {**ui.TYPE_ABBR, "inductor-ferrite": "L", "diode-zener": "D", "diode-thyrector": "D",
                "transistor-FET": "Q", "IC": "U", "IC-voltage-reg": "U", "opamp": "U",
                "opamp-schmitt": "U"}

# Annotation-cost log: one line per save with a wall-clock timestamp. Per-image effort is
# the gap between consecutive saves within a session (gaps over 15 min count as breaks).
TIMING = AUDIT / "timing_log.jsonl"
_orig_save = ui.save


def _timed_save(img_id, nets, verified, excluded=False):
    ok = _orig_save(img_id, nets, verified, excluded)
    with TIMING.open("a") as f:
        f.write(json.dumps({"t": time.time(), "id": img_id, "verified": bool(verified),
                            "excluded": bool(excluded), "n_nets": len(nets)}) + "\n")
    return ok


ui.save = _timed_save

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    if not ui.CLEAN.is_dir():
        raise SystemExit(f"missing {ui.CLEAN}: stage it with cghd_audit_export.py (images are not in git)")
    print(f"CGHD-reference audit UI -> http://127.0.0.1:{port}/   (editing {ui.GT})")
    ThreadingHTTPServer(("127.0.0.1", port), ui.H).serve_forever()
