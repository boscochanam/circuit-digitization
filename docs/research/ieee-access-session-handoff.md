# IEEE Access paper push — session handoff (2026-06-27)

Persistent state for continuing the IEEE Access paper overhaul. Read this first next session.

## Goal
Make `paper/ieee-paper/paper.tex` submittable to **IEEE Access**: correct template, thicker
related work, close the real-data join-validation gap, substantiate the VLM motivation with a
first-party Claude experiment, position vs 2026 prior work. Approved plan:
`~/.claude/plans/flickering-waddling-deer.md`.

## TL;DR status
- Paper content + template conversion: **largely done** (`paper-access.tex`).
- Synthetic VLM experiment: **done** (F1 0.99 — clean-condition control).
- Real VLM + real join table: **run, but against UNVERIFIED, biased net-GT** — numbers are
  preliminary until the human verification step completes.
- **Hard blocker:** human-verify the 10-image net-level GT (user is doing this). Everything
  real re-runs against it afterward.

## Two findings that reshaped the paper (both reflected honestly in paper-access.tex)
1. **VLMs do connectivity better than the original "omits 26–67%" claim.** Real end-to-end
   (raw scan, Claude Opus 4.8) ≈ **F1 0.79** (declines with complexity; component detection
   near-perfect → the gap is connectivity). Far above DiagramNet's Claude-Sonnet-4 (0.265)
   because our circuits are simpler + stronger model + heavy test-time compute + forgiving
   pair-F1 + position-matching. → Motivation reframed to: **cost (~10^5 tokens/image),
   degrades with complexity, no structural guarantee, non-simulatable output** + DiagramNet's
   collapse on complex diagrams. Framing chosen by user: **clean-control (0.99) + real-gap**.
2. **degree_budget may NOT be the best real-image strategy.** On 10 images it scored **below
   graph_rescue** (0.825 vs 0.878). Completion (b-matching) seems to over-merge on noisy
   *detected* wires — opposite of its synthetic-L4 win (0.94). Decision: **flagged as an open
   question** in paper Limitations (done). Confirm/retract after GT verification.

## Numbers so far (ALL real numbers vs UNVERIFIED, graph_scale-biased GT — re-run after verify)
- **Synthetic VLM connectivity** (15 circuits): mean F1 **0.99** (14/15 perfect; two_sources 0.89). 0% connections omitted. TRUSTWORTHY (GT is authored).
- **Real VLM end-to-end** (10 imgs): mean F1 **0.79** (P0.78/R0.85), 19% pairs omitted.
  Per-image: C20 1.00, C109 1.00, C29 0.89, C15 0.88, C84 0.75, C138 0.75, C21 0.71, C28 0.69, C92 0.67, C22 0.59.
- **Real VLM given-detections** (3-img pilot): C20 1.00, C29 0.81, C84 0.75; mean **0.86**.
- **Real join F1** (10 imgs, same pair-F1 metric): graph_scale 0.958 **(CIRCULAR — it generated the GT, ignore for ranking)**, graph_rescue 0.878, degree_budget 0.825, production 0.650.
- **External (cite):** SINA (arXiv 2601.22114, DATE 2026) 96.47% netlist acc, 2.72×. DiagramNet (2605.01338) connection F1: GPT-5 0.029, Claude-Sonnet-4 0.265, Gemini-2.5-Pro 0.008, tuned-3B 0.735.

## ⚠️ Methodological caveat (critical)
Net-GT was bootstrapped with the **graph_scale** join over PERFECT GT wires. This **biases the
join ranking toward graph_scale** (it can't be fairly ranked against a GT it made) and makes all
real numbers provisional. The ONLY fix is human-verified GT — no automatic GT is independent of
the strategies under test. Both VLM and join real numbers depend on this.

## THE BLOCKER — human net-GT verification (user task, in progress)
On **claw** (`ssh claw@192.168.1.22`, repo `/home/claw/circuit-digitization`):
- Overlays: `output/net_gt_overlays/*.png` (red number = component index; colored dots = proposed net per pin)
- Checklist: `ground_truth/verify_sheet.md` (each net as component-index groups + types)
- Edit `ground_truth/real_nets.json`; set `"source": "human-verified"` when done.
The 10 clean images: C84_D2_P1, C22_D2_P3, C29_D2_P4, C15_D2_P2, C20_D2_P2, C138_D1_P3, C92_D1_P3, C109_D2_P3, C21_D1_P3, C28_D1_P3.

## NEXT STEPS (after GT verified)
1. Re-pull verified `real_nets.json` from claw.
2. **Re-score VLM** (responses already saved, no need to re-run subagents):
   `python -m wire_detection.benchmark.vlm_connectivity_eval wire_detection/benchmark/data/vlm_responses_real_e2e.json --real ground_truth/real_nets.json --e2e`
   and `... vlm_responses_real_given_detections.json --real ...` (no --e2e).
3. **Re-run real join table** on claw:
   `./.venv/bin/python -m wire_detection.benchmark.join_eval_real_f1 --gt ground_truth/real_nets.json`
   → confirm/retract the degree_budget < graph_rescue finding; set the honest real-image default.
4. **Finish paper (Workstream F/G, task #7):** write the VLM experiment section (0.99 control +
   real-gap), add comparison tables (ours vs SINA/DiagramNet; real join table), reframe motivation,
   loosen the dense abstract sentence, add 36-config sweep appendix. Wire final numbers in.
5. Optionally scale net-GT beyond 10 images (conservative join + verify) for stronger stats.

## Author-supplied (cannot automate)
ORCIDs, author biographies, funding source — placeholders in `paper-access.tex`.
Compile `paper-access.tex` on **Overleaf IEEE Access template** (bundles `ieeeaccess.cls`; no
LaTeX on bosco or claw).

## File inventory
**New (this session):**
- `wire_detection/synthgt/render.py` — clean synthetic schematic renderer
- `wire_detection/benchmark/vlm_connectivity_eval.py` — VLM prompt/parse/score (synthetic, real-given-detections, real-e2e via --e2e)
- `wire_detection/benchmark/build_net_gt.py` — net-GT builder (GT_STRATEGY="graph_scale"), overlays, VLM-input overlays, component metadata
- `wire_detection/benchmark/join_eval_real_f1.py` — real join connectivity-F1 vs net-GT
- `wire_detection/benchmark/data/vlm_responses_synthetic.json` (15) — F1 0.99
- `wire_detection/benchmark/data/vlm_responses_real_e2e.json` (10) — F1 0.79
- `wire_detection/benchmark/data/vlm_responses_real_given_detections.json` (3) — F1 0.86
- `paper/ieee-paper/paper-access.tex` — IEEE Access conversion (+ Data&Code Availability + degree_budget caveat)

**Modified:**
- `paper/ieee-paper/paper.tex` — 5 edge types, softened VLM claim, Related Work 6→23 refs (SINA/DiagramNet/AMSnet2.0/AMSBench/Masala-CHAI/instance-seg/JUHCCR/LLM4EDA + grounding; removed off-topic alam2022survey)
- `README.md`, `AGENTS.md` — doc-sync (default strategy, F1 eval explainer, removed stale scikit-learn gotcha)
- `wire_detection/core/join_graph.py` — docstring 5 edge types
- `wire_detection/synthgt/evaluate.py` — DEFAULT_STRATEGY re-exports join_strategies (was stale "graph_rescue")
- `wire_detection/benchmark/netlist_exploration.py` — removed dup "diac" dict key
- `pyproject.toml` — added [tool.mypy] (was fully broken: dual-module error)
- ~65 files — `ruff --fix` cosmetic (unused imports etc.)

**On claw (`/home/claw/circuit-digitization/`):** `ground_truth/real_nets.json` (10-img proposals, UNVERIFIED), `ground_truth/verify_sheet.md`, `output/net_gt_overlays/*.png`, `output/vlm_input_overlays/*.png`, `output/join_eval_real_f1.json`; new scripts synced under `wire_detection/benchmark/` + `synthgt/`.

## Environment notes
- **bosco (this machine):** synthetic-only (no CGHD data, no model). `uv run` works. **Bash sandbox blocks network/ssh — use `dangerouslyDisableSandbox: true` for ssh/scp/uv sync.** Tests: 477 pass.
- **claw (192.168.1.22):** has CGHD data (`/home/claw/workspace/ground_truth/labels_few_annot/`), `roboflow_test2/`, and the YOLO model. **NO uv — use `./.venv/bin/python`.** git remote `chris` = github.com/ChrisDc777/circuit-digitization.
- VLM = **Claude Code subagents** (general-purpose, fresh/no-context), one per image; responses saved to benchmark/data/. Re-running needs raw scans re-pulled from claw to a local dir (scratchpad is ephemeral).
- Connectivity metric = component-pair F1 (`intended_pairs`/`_prf` semantics), restricted to SPICE-active components (SIMULATABLE_PREFIXES R/C/L/V/D/Q/U). Synthetic labels encode idx+1 (R2→idx1); real overlays/e2e use raw indices / position-matching (zero_based).

## Nothing committed
All work is uncommitted on `main`. Conference `paper.tex` still compiles. Decide commit/branch next session.
