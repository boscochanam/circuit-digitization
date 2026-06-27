# IEEE Access paper push — session handoff (updated 2026-06-28)

Persistent state for continuing the IEEE Access paper overhaul. **Read this first.**
Supersedes the 2026-06-27 version. Project memory: `ieee-access-paper-push.md`.

## Goal
Make `paper/ieee-paper/paper-access.tex` submittable to IEEE Access: correct template, thicker
related work, **close the real-data join-validation gap with human-verified net-level GT**,
substantiate the VLM motivation with a first-party Claude experiment, position vs 2026 prior
work.

---

## TL;DR current status (2026-06-28)
- **Net-level GT: 33 images human-verified by the user** (via a custom local UI). 1 left
  (C167_D2_P1). This is the big unblock — real numbers are now trustworthy.
- **Join-strategy ranking settled at N=33: degree_budget WINS** (the promoted flagship is
  vindicated). graph_scale's earlier N=9 lead was small-sample noise.
- **VLM connectivity re-scored against verified GT: F1 0.90** (was 0.79 vs the biased GT) —
  but still only N=9 (new images lack VLM responses).
- **Two GT bugs found & fixed this session** (see below): a methodological circularity, and a
  roboflow rotated-label bug.
- **Remaining:** 2 edit-slips to fix + re-run, optionally finish C167 and scale VLM to N=33,
  then write the paper sections + tables. Author still owes ORCIDs/bios/funding.

---

## RESULTS (numbers to use in the paper)

### Join strategies — real images, connectivity component-pair F1
| strategy | N=9 (initial) | **N=33 (verified, use this)** |
|----------|---------------|-------------------------------|
| **degree_budget** | 0.811 | **0.845  ← best** |
| graph_scale | 0.851 | 0.811 |
| graph_rescue | 0.794 | 0.803 |
| production | 0.631 | 0.676 |

- degree_budget vs graph_scale head-to-head (N=33): **db wins 13, ties 15, gs wins 5**, mean
  paired diff +0.034. Robust, not outlier-driven.
- degree_budget won **despite** the GT being seeded by graph_scale (bias would favor gs) →
  result is conservative/strong.
- Caveat: 2 edit-slips still in the GT (C8_D1_P3, C105_D1_P4) — C105 inflates db's biggest
  win; fix and re-run for the final clean number (won't change the ranking).

### VLM (Claude Opus 4.8) connectivity
| | precision | recall | F1 |
|---|---|---|---|
| Synthetic control (15 circuits, authored GT) | — | — | **0.99** |
| Real end-to-end vs **biased** GT (N=9) | 0.78 | 0.85 | 0.79 |
| Real end-to-end vs **verified** GT (N=9) | **0.95** | **0.87** | **0.90** |

VLM precision ≈0.95 (rarely invents a wrong connection); it *misses* pairs on complex
circuits (recall 0.87, 15% of GT pairs omitted). Strengthens the "VLMs CAN do connectivity but
cost/scale/no-guarantee" motivation. **External cites:** SINA (arXiv 2601.22114, DATE 2026)
96.47% netlist acc; DiagramNet (2605.01338) connection-F1 GPT-5 0.029 / Claude-Sonnet-4 0.265.

---

## ⚠️ BUG 1 — Methodological circularity (Claude must NOT be GT verifier)
The paper benchmarks a **VLM = Claude Opus 4.8**. If Claude also verifies the net-GT, the
answer key is written by the model under test → VLM score is self-flattered (shared visual
bias). **Decision (user's call): the USER is verifier of record; Claude only PRE-SCREENS.**
- Claude IS independent of the *join algorithms* (it reads pixels, doesn't run union-find), so
  Claude's trace is valid for ranking the join table — but NOT for the VLM comparison.
- Claude's pre-screen used the **graph_scale-colored overlay**, which can reveal graph_scale's
  *isolated* parts but **structurally cannot reveal its over-splits / mis-joins**. The human
  pass caught real graph_scale errors Claude missed (C84 rail wrongly split; C29 bridge load
  mis-placed). This is *why* human verification is required, and it materially changed results.

## ⚠️ BUG 2 — Roboflow rotated/augmented labels (FIXED) — **document, the user asked**
**Symptom:** component boxes/labels wrong & misaligned on many new-batch images.
**Root cause:** two data sources must align —
- component boxes ← roboflow HDC labels (`roboflow_test2/{train,valid,test}/labels/<name>_jpg.rf.<hash>.txt`, OBB format)
- image + wires ← CGHD `labels_few_annot` (`GT_IMAGES`, `GT_WIRE_LABELS`)

Roboflow exports **multiple AUGMENTED copies per image** (rotations/flips/shifts), each a
`<name>_jpg.rf.<hash>.txt` with a matching `.rf.<hash>.jpg`. The old `find_hdc_label` returned
`sorted(matches)[0]` — the lexicographically-first hash, often a **rotated** copy → boxes for a
transformed image laid over the original → misaligned/"wrong" labels. (Counts seen: C37 had 4
copies, C5/C84/C133 had 2, etc.)
**Fix (in `wire_detection/benchmark/build_net_gt.py::find_hdc_label`, UNCOMMITTED):** among all
copies, pick the **identity** one whose `.rf.<hash>.jpg` matches `GT_IMAGES/<name>_jpg.jpg`
(min mean abs pixel diff ≈ 0). Falls back to first match if no image comparison possible.
**Audit result:** original 10 were 0/10 affected (matches[0] happened to be identity → the
verified-9 GT + VLM 0.90 + N=9 join table all STAND). New batch was **9/25 wrong** before fix,
0/25 after. Diagnostics written: `check_align.py` (ink fraction inside each box), `audit_picks.py`
(current vs identity pick), `probe_identity.py` (per-copy ink + image-match).
**OBB & class mapping are NOT bugs:** `parse_components` takes the axis-aligned box of the 4 OBB
points (correct); `COMPONENT_TYPES` int→type mapping verified correct against drawn symbols.

## Component-class categorization (used to exclude bad circuits) — **the user asked**
roboflow `data.yaml` class order is alphabetical-ish (0:and, 1:antenna, 2:capacitor-adjustable,
…); `COMPONENT_TYPES` mirrors it correctly. `SIMULATABLE_PREFIXES = {R,C,L,V,D,Q,U}`.
- **SPICE-active (scored):** resistor, capacitor-{unpolarized,polarized,adjustable}, inductor,
  inductor-ferrite, voltage-{DC,AC,battery}, diode, diode-LED, diode-zener, diode-thyrector,
  transistor-BJT, transistor-FET, opamp, opamp-schmitt, IC, IC-NE555, IC-voltage-reg.
- **Structural / ignore (not a circuit element):** junction, terminal, gnd, crossover, wire,
  text, vss; (probe*, antenna treated as structural too).
- **OTHER real devices → EXCLUDE the whole circuit:** and/nand/nor/not/or/xor, triac, diac,
  fuse, varistor, thyristor, relay, switch, transformer, lamp, motor, speaker, microphone,
  crystal, optocoupler, resistor-adjustable, resistor-photo, transistor-photo, optical,
  magnetic, mechanical, socket, unknown.
`gen_batch.py::is_clean()` drops any circuit containing an OTHER device (filtering them would
leave an unrepresentative net-GT, e.g. C157 = 3 inductors + a filtered-out triac/fuse/varistor).
**Clean pool = 48 of 134 images.**
**Known gaps:** (a) a **switch** affects connectivity but is excluded — if switches should be
nodes, that's a deliberate change to make; (b) genuinely *unlabeled* components (roboflow never
boxed them) can't be auto-detected → the UI has a manual **exclude** button for those.

---

## THE VERIFICATION UI (how the human verified)
Run from repo root: `python wire_detection/benchmark/gt_verify_ui.py 8765` → http://127.0.0.1:8765/
(stdlib only; bosco `.venv/bin/python`). Reads/edits `ground_truth/real_nets_working.json`,
overlays from `ground_truth/net_gt_ui_overlays/`, bboxes from `ground_truth/net_gt_ui_meta.json`.
Features: clean wires-only image with client-drawn labelled boxes (R2/C8/Q1 — identical to the
side panel), zoom/pan, click-to-select, per-net colored connector lines that fill solid when you
tick **mark ✓**, "N/M reviewed" progress, parts go green when done, **auto-advance**, keyboard
(←/→ images, `v` save+verify), and an **✗ exclude** button (bad/unlabeled circuits).
Default view is the **neutral** image (no graph_scale coloring) to avoid biasing the human.
Saving writes **electrical-only nets** back (`[[ci,"e"],…]`); scoring ignores pin names &
non-electrical pins (verified in both eval scripts). Excluded imgs get `source="excluded-…"`.

---

## SCORING — how nets become numbers
Both evals reduce nets to **connected electrical-component PAIRS** (restricted to
`electrical_idxs`) and P/R/F1 vs GT pairs (`itertools.combinations` per net). Pin names and
non-electrical pins are ignored — so the UI's electrical-only edits are sufficient.
- `join_eval_real_f1.py --gt <file>` (run on **claw**: needs YOLO model + detected wires):
  detects wires, runs each of `[degree_budget, graph_rescue, graph_scale, production]`, scores.
- `vlm_connectivity_eval.py <responses.json> --real <gt> --e2e` (run on **bosco**: no model):
  scores saved VLM responses. e2e responses only exist for the original 10 imgs.

---

## NEXT STEPS (in order)
1. **User:** fix 2 edit-slips in UI then tell Claude to re-run join eval:
   - C8_D1_P3: transistor in 4 nets (remove from one group).
   - C105_D1_P4: IC isolated (connect it).  Optionally finish C167_D2_P1.
2. **Re-pull** `real_nets_working.json` from bosco repo → rebuild `real_nets_verified.json`
   (images with `human-verified` in source, drop excluded) → push to claw → re-run join eval.
3. **(Optional) Scale VLM to N=33:** re-run VLM subagents (general-purpose, fresh, one per
   image) on the new images' raw scans + the vlm_input overlays, save to
   `wire_detection/benchmark/data/vlm_responses_real_e2e.json`, re-score. Currently VLM = N=9.
4. **Write paper (Workstream F/G):** VLM section (0.99 control + 0.90 real, P0.95/R0.87),
   comparison tables (ours vs SINA/DiagramNet; the N=33 join table), reframe motivation to
   cost/scale/no-guarantee/non-simulatable, add 36-config sweep appendix, loosen dense abstract
   sentence. Wire in final numbers.
5. **Commit** the uncommitted fix + new tooling (see file inventory). Compile `paper-access.tex`
   on Overleaf IEEE Access template (no LaTeX on bosco/claw).

---

## FILE INVENTORY (persisted this session)
**Repo `wire_detection/benchmark/` (NEW tooling, uncommitted):**
- `gt_verify_ui.py` — the verification UI (repo-relative paths).
- `gen_batch.py` — select clean circuits (is_clean) + build proposals + clean overlays + bboxes.
- `render_verify.py` (graph_scale-colored overlay), `render_neutral.py` (neutral overlay),
  `export_meta.py` (bboxes + wires-only overlay), `check_align.py` / `audit_picks.py` /
  `probe_identity.py` (roboflow-alignment diagnostics).
**Repo `wire_detection/benchmark/build_net_gt.py`** — `find_hdc_label` identity-selection FIX
(uncommitted). Also the earlier GT_STRATEGY="graph_scale" bootstrap.
**Repo `ground_truth/`:** `real_nets_verified.json` (33 verified), `real_nets_working.json`
(34, what the UI edits — has the 1 to-do + the 2 slips), `net_gt_ui_meta.json` (bboxes),
`net_gt_ui_overlays/*.png` (34 wires-only overlays), `PRESCREEN_FINDINGS.md` (early pre-screen).
**On claw `/home/claw/circuit-digitization/`:** all the above scripts synced;
`ground_truth/real_nets_verified.json`; `output/net_gt_*` overlays. claw has CGHD data + model.
**VLM responses (bosco repo `wire_detection/benchmark/data/`):** vlm_responses_synthetic.json
(15), vlm_responses_real_e2e.json (10), vlm_responses_real_given_detections.json (3).

## Environment notes
- **bosco (this machine):** synthetic-only (no CGHD data/model). `uv run` / `.venv/bin/python`.
  Bash sandbox **blocks network/ssh — use `dangerouslyDisableSandbox: true`** for ssh/scp.
  `pkill`/`kill` are sandbox-restricted (use `dangerouslyDisableSandbox`); note `pgrep -f
  gt_verify_ui` matches your own command line — check the actual port instead.
- **claw (`ssh claw@192.168.1.22`, `/home/claw/circuit-digitization`):** CGHD data
  (`/home/claw/workspace/ground_truth/labels_few_annot/`), `roboflow_test2/`, YOLO model.
  **NO uv — use `./.venv/bin/python`.** git remote `chris` = github.com/ChrisDc777/...
- Scratchpad is **ephemeral** — everything important was copied into the repo (above).
- VLM = Claude Code subagents (general-purpose, fresh/no-context), one per image.
