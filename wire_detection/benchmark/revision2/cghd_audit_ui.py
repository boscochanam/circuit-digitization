#!/usr/bin/env python3
"""Serve the existing net-GT verification UI on the CGHD-reference audit batch.

Reuses wire_detection/benchmark/gt_verify_ui.py unchanged; only its module-level paths are
redirected to ground_truth/cghd_ref_audit/ (so ground_truth/real_nets_working.json is never
edited) and the part-label table is extended to every electrical type in the batch.

  python -m wire_detection.benchmark.revision2.cghd_audit_ui [port] [--recheck]   # default 8766
Verified entries get source "human-verified (UI)" in ground_truth/cghd_ref_audit/real_nets_working.json;
the original reference nets are kept under "_nets_original" by the UI's save().
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from http.server import ThreadingHTTPServer

from wire_detection.benchmark import gt_verify_ui as ui

AUDIT = ui.ROOT / "ground_truth" / "cghd_ref_audit"
ui.GT = AUDIT / "real_nets_working.json"
ui.CLEAN = AUDIT / "overlays"
ui.META = json.loads((AUDIT / "net_gt_ui_meta.json").read_text())
ui.WIREMAP = AUDIT / "wiremap"   # built by revision2/net_ui_wiremap.py --set audit
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

# Toggle between overlays with gray context boxes (overlays/) and plain photos
# (overlays_plain/), also hiding the canvas (blue boxes, net lines), so nothing hides the
# wires. Button or key "g".
PLAIN = AUDIT / "overlays_plain"
_TOGGLE_JS = r"""
<script>
let showParts=true;
const _origLoad=load;
load=function(i){_origLoad(i);if(!showParts)im.src='/plain/'+D().name+'.png';};
function togglePartBoxes(){showParts=!showParts;
  document.getElementById('ptog').textContent=showParts?'hide all overlays':'show overlays';
  cv.style.visibility=showParts?'visible':'hidden';
  im.onload=()=>{redraw();};im.src=(showParts?'/clean/':'/plain/')+D().name+'.png';}
document.getElementById('ptog').onclick=togglePartBoxes;
window.addEventListener('keydown',e=>{if(e.target.tagName=='INPUT')return;if(e.key=='g')togglePartBoxes();});
</script>"""
ui.HTML = ui.HTML.replace("<button id=fit>reset view</button>",
                          "<button id=fit>reset view</button> <button id=ptog>hide all overlays</button>", 1)
ui.HTML = ui.HTML.replace("</body>", _TOGGLE_JS + "</body>", 1) if "</body>" in ui.HTML else ui.HTML + _TOGGLE_JS


# Blind model pre-screen: images where the model's trace agrees with the proposal are hidden
# from the to-do list (they stay in the JSON, unverified); disagreements and untraced images
# show the model's note in the side panel.
# --recheck: human check of the images the model pre-screen settled. Every unverified,
# non-excluded image is listed and model notes are hidden, so the check stays blind.
RECHECK = "--recheck" in sys.argv
MODEL = AUDIT / "model_check.json"
if MODEL.exists() and not RECHECK:
    _mc = json.loads(MODEL.read_text())["images"]
    ui.FLAGS = {k: ("MODEL CHECK: " + v["note"]) for k, v in _mc.items() if v["status"] != "agree"}
    _orig_state = ui.state

    def _state():
        st = _orig_state()
        st["images"] = [x for x in st["images"]
                        if x["verified"] or x["excluded"] or _mc.get(x["id"], {}).get("status") != "agree"]
        return st

    ui.state = _state


class H(ui.H):
    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/plain/"):
            f = PLAIN / Path(p[len("/plain/"):]).name
            if f.exists():
                return self._send(200, f.read_bytes(), "image/png")
            return self._send(404, b"no img", "text/plain")
        return super().do_GET()

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--recheck"]
    port = int(args[0]) if args else 8766
    if not ui.CLEAN.is_dir():
        raise SystemExit(f"missing {ui.CLEAN}: stage it with cghd_audit_export.py (images are not in git)")
    print(f"CGHD-reference audit UI -> http://127.0.0.1:{port}/   (editing {ui.GT})")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
