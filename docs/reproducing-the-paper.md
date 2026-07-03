# Reproducing the Paper

This page maps each claim, table, and figure in *"From Hand-Drawn Schematics to
SPICE Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a
Human-Verified Connectivity Benchmark"* to the artifact and command that
produces it. It expands the paper's **Data and Code Availability** section into a
step-by-step reviewer guide.

All commands are run from the repository root. Use `uv run python ...` (the
project pins its environment via `uv`); on machines without `uv` substitute
`./.venv/bin/python`.

Three tiers of reproducibility, in increasing order of external data required:

1. **Zero external data** — the synthetic suite and the committed result
   artifacts. Runs on a clean checkout.
2. **Committed VLM responses / result JSONs** — score saved model outputs and
   recompute confidence intervals. Runs on a clean checkout.
3. **External data (CGHD-1152 + the component model)** — regenerate the
   detected-wire and end-to-end numbers from images. Requires the ~4 GB CGHD
   dataset and the 47.8 MB YOLO model.

---

## 1. What reproduces from this repo alone

### Synthetic robustness suite (zero external data)

The authored-circuit suite generates its own images and ground truth, so it needs
no dataset and no model. It backs **Table II** (synthetic leaderboard),
**Table IV** (per-circuit at L4), and the Fig. 6 robustness bars.

```bash
# Full report for the default strategy (scale_completion)
uv run python -m wire_detection.synthgt

# Table II — rank every join strategy on ground truth (join-only leaderboard)
uv run python -m wire_detection.synthgt --compare --seeds 8

# Table IV — per-circuit, one strategy, 16 seeds
uv run python -m wire_detection.synthgt -s 16
```

SPICE columns require `ngspice` (set `NGSPICE_PATH`); without it, the join
scores still run. The error model is a deliberately-labelled placeholder (see the
CLI caveat and `docs/synthetic-eval-plan.md`).

### Score saved VLM responses (no model needed)

The Claude-VLM connectivity experiment is decoupled into "get responses" and
"score responses". The scoring phase runs against the committed responses and the
human-verified ground truth with no external data. This backs the **VLM row of
Table III** and the synthetic VLM control.

```bash
# VLM on real images, end-to-end (raw scan), vs verified GT
uv run python -m wire_detection.benchmark.vlm_connectivity_eval \
    wire_detection/benchmark/data/vlm_responses_real_e2e.json \
    --real ground_truth/real_nets_verified.json --e2e

# VLM synthetic control (authored GT)
uv run python -m wire_detection.benchmark.vlm_connectivity_eval \
    wire_detection/benchmark/data/vlm_responses_synthetic.json
```

**Honest caveat on N.** The committed raw responses
(`wire_detection/benchmark/data/vlm_responses_real_e2e.json`) are the original
**N=9** set (mean F1 ≈ 0.90). The paper's headline **N=31** VLM number
(micro-F1 0.923) was produced by a later clean re-run whose *scored* per-image
counts are committed as `docs/research/experiments/vlm_clean_rerun_n31.json`; the
31 raw response bodies for that run are not all committed. The bootstrap step
below consumes the N=31 scored artifact directly.

### Bootstrap confidence intervals (committed artifacts only)

`bootstrap_ci.py` reads the committed per-image count artifacts
(`join_micro_n31.json`, `vlm_clean_rerun_n31.json`) and recomputes the 95% CIs
and the paired ours-vs-VLM difference. Pure stdlib; runs on a clean checkout.

```bash
uv run python -m wire_detection.benchmark.bootstrap_ci
# writes docs/research/experiments/bootstrap_ci_n31.json
```

This reproduces the paired micro-F1 difference **+0.033, 95% CI [−0.009, +0.078]**
quoted in the abstract and Fig. 7 caption.

### Committed result artifacts

The final numbers are stored as JSON under `docs/research/experiments/`, so every
table/figure value can be inspected without re-running anything:

| Artifact | Contents |
|---|---|
| `join_micro_n31.json` | Join strategies, real detected wires, micro/macro + per-image counts (Table III core) |
| `cc_detected_micro_n31.json` | Connected-component baseline on identical detected wires (Table III) |
| `hough_micro_n31.json` | Hough + proximity baseline sweep (Table III) |
| `fair_join_comparison_n31.json` | Detected vs perfect-GT wires (the "detection is not the bottleneck" claim) |
| `detection_ceiling_n31.json` | Perfect-wire ceiling artifact |
| `bootstrap_ci_n31.json` | 95% bootstrap CIs + paired VLM−ours difference |
| `synthetic_leaderboard.json` | Table II synthetic leaderboard |
| `per_circuit_scale_completion_l4_n16.json` | Table IV per-circuit at L4, 16 seeds |

---

## 2. What needs external data

### The component-detection model

The end-to-end and detected-wire evaluations need the YOLO26m-OBB component
detector. Download and verify it with:

```bash
uv run python scripts/download_model.py
# -> models/component_detection/yolo26m_obb_16class_aug.pt (47.8 MB)
```

The script fetches from
`https://huggingface.co/boscochanam/circuit-component-detector` and checks the
SHA256 recorded in `docs/datasets.md`. It is idempotent (skips if already valid).

### CGHD-1152 dataset

The wire benchmark and the real-image join eval read CGHD-1152 images. Stage the
dataset as described in [Datasets → Setup](datasets.md):

```bash
curl -L -o ~/Downloads/cghd1152.zip \
  https://www.kaggle.com/api/v1/datasets/download/johannesbayer/cghd1152
# unzip to ./cghd1152/ (see datasets.md for the expected layout)
```

### 134-image wire-detection benchmark (Table I / Fig. 5)

```bash
# Regenerates the wire-detection F1 sweep across 134 images.
uv run python -m wire_detection.benchmark.expanded_benchmark
```

**Not dry-runnable here (claw-only).** `expanded_benchmark.py` hard-codes
absolute data paths under `/home/claw/...` (see the `GT_LABELS` / `GT_IMAGES` /
`HDC_BASE` constants near the top) and has no argparse; it must be run on the
data host or with those constants edited to your paths. It backs the F1 = 0.976
headline (Sauvola + 16 px anchor).

### Real-image join eval + baselines (Table III), on detected wires

These detect wires from CGHD images (needs the model and CGHD staged), run each
join strategy, and score component-pair F1 against the verified GT. Run on the
data host (`./.venv/bin/python`):

```bash
# Table III — join strategies (pass scale_completion explicitly: the default
# strategy list is degree_budget,graph_rescue,graph_scale,production and does
# NOT include the promoted scale_completion; use --strategies all for every one)
./.venv/bin/python -m wire_detection.benchmark.join_eval_real_f1 \
    --gt ground_truth/real_nets_verified.json \
    --strategies scale_completion,degree_budget,graph_scale,graph_rescue,production \
    --out docs/research/experiments/join_micro_n31.json

# Table III — connected-component baseline on the SAME detected wires
./.venv/bin/python -m wire_detection.benchmark.cc_baseline_detected \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/cc_detected_micro_n31.json

# Table III — Hough + proximity classical baseline (config sweep)
./.venv/bin/python -m wire_detection.benchmark.hough_baseline \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/hough_micro_n31.json

# Detection-is-not-the-bottleneck: detected vs perfect GT wires
./.venv/bin/python -m wire_detection.benchmark.detection_ceiling \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/fair_join_comparison_n31.json
```

**Not dry-runnable on the doc-authoring host** (no CGHD data or model there); the
argparse flags above were read from each script's source, not executed. The
`--strategies` caveat is verified from `join_eval_real_f1.py` (its `STRATEGIES`
default omits `scale_completion`).

---

## 3. The human-verification workflow

The 31-image net-level ground truth was produced by a human using a local
browser UI. It reads the working GT and per-image wires-only overlays and writes
electrical-net membership back.

```bash
uv run python wire_detection/benchmark/gt_verify_ui.py 8765
# open http://127.0.0.1:8765/
```

- **Reads:** `ground_truth/real_nets_working.json` (the working file it edits),
  `ground_truth/net_gt_ui_overlays/*.png` (wires-only overlays, 34 committed),
  `ground_truth/net_gt_ui_meta.json` (component bounding boxes).
- **Writes:** edits back to `real_nets_working.json` as electrical-only nets
  (`[[ci, "e"], ...]`); scoring ignores pin names and non-electrical pins.
- **UI:** neutral wires-only base image with client-drawn labelled boxes
  (R2/C8/Q1, matching the side panel), zoom/pan, click-to-select, per-net
  coloured connectors that fill solid on **mark ✓**, "N/M reviewed" progress,
  auto-advance, keyboard (`←/→` images, `v` = save + verify), and an **✗ exclude**
  button for bad/unlabeled circuits. The default view is neutral (no
  strategy-coloured overlay) to avoid biasing the human.

The verified export used by every eval is
`ground_truth/real_nets_verified.json`. Stdlib only; runs on a clean checkout.

**Design note (why humans, not the VLM, are the verifier of record).** Because the
paper benchmarks Claude as a VLM, Claude must not also write the answer key, or
its score is self-flattered. Claude only pre-screened (using a strategy-coloured
overlay that structurally cannot reveal over-splits/mis-joins); the human pass
caught real errors the pre-screen missed. See the session handoff doc for detail.

---

## 4. Table / figure → script + artifact map

| Paper item | Generating script(s) | Committed artifact | External data? |
|---|---|---|---|
| **Table I** — Wire detection (134 images), Fig. 5 | `wire_detection/benchmark/expanded_benchmark.py` | — (F1 0.976 reported in text) | CGHD + model |
| **Table II** — Synthetic join leaderboard | `python -m wire_detection.synthgt --compare` | `synthetic_leaderboard.json` | none |
| **Table III** — Real join + baselines + VLM | `join_eval_real_f1.py`, `cc_baseline_detected.py`, `hough_baseline.py`; VLM via `vlm_connectivity_eval.py --e2e` | `join_micro_n31.json`, `cc_detected_micro_n31.json`, `hough_micro_n31.json`, `vlm_clean_rerun_n31.json` | join/baseline rows need CGHD + model; VLM scoring row does not |
| **Table IV** — Per-circuit at L4 (16 seeds) | `python -m wire_detection.synthgt -s 16` | `per_circuit_scale_completion_l4_n16.json` | none |
| **Fig. 6** — Robustness under error injection | `python -m wire_detection.synthgt --compare` | `synthetic_leaderboard.json` | none |
| **Fig. 7** — Micro-F1 bars + VLM band + CIs | `bootstrap_ci.py` (CIs); bars from the Table III artifacts | `bootstrap_ci_n31.json` | none (consumes committed artifacts) |
| "Detection is not the bottleneck" | `detection_ceiling.py` | `fair_join_comparison_n31.json`, `detection_ceiling_n31.json` | CGHD + model to regenerate |

Commands marked in §2 as claw-only were transcribed from each script's argparse
and docstring, not executed on the doc host. All §1 and §3 commands were
dry-run on a clean checkout.
