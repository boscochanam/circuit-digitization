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

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    if not ui.CLEAN.is_dir():
        raise SystemExit(f"missing {ui.CLEAN}: stage it with cghd_audit_export.py (images are not in git)")
    print(f"CGHD-reference audit UI -> http://127.0.0.1:{port}/   (editing {ui.GT})")
    ThreadingHTTPServer(("127.0.0.1", port), ui.H).serve_forever()
