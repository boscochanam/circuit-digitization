# Reproducing the Paper

This page maps claims in *"From Hand-Drawn Schematics to Structural Circuit
Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a
Human-Verified Connectivity Benchmark"* (IEEE Access, Access-2026-33821, revised
manuscript) to the artifact and command that produces them. Table and figure
numbers follow the current `paper/ieee-paper/paper-access.tex`. It expands the
paper's **Data and Code Availability** section into a step-by-step reviewer
guide. The revision-2 experiments (paired tests, rescaling, end to end,
held-out benchmark, audit) are in [section 5](#5-revision-2-experiments).

All commands are run from the repository root. Use `uv run python ...` (the
project pins its environment via `uv`); on machines without `uv` substitute
`./.venv/bin/python`.

Three tiers of reproducibility, in increasing order of external data required:

1. **Zero external data** — the synthetic suite and the committed result
   artifacts. Runs on a clean checkout.
2. **Committed VLM responses / result JSONs** — score saved model outputs and
   recompute confidence intervals. Runs on a clean checkout.
3. **External data (CGHD-1152, CGHD v12 + the component model)** — regenerate
   the detected-wire, held-out and end-to-end numbers from images. Requires the
   ~4 GB CGHD-1152 dataset, CGHD v12 from Zenodo (10.5281/zenodo.10056817) for
   the held-out benchmark, and the 47.8 MB YOLO model.

---

## Local-only review inputs (supplement to GitHub)

[Download the Google Drive supplement](https://drive.google.com/file/d/1fIM2fxTW5bEsbaWL1nSKS3ZlmauJSNjx/view?usp=drivesdk).
It contains **only** two PDFs absent from the repository: the old manuscript
snapshot used for the alternating review comparison
(`old_snapshot_NOT_PORTAL_VERIFIED.pdf`) and the locally generated
highlighted-PDF input (`current_highlighted.pdf`), plus a README and checksums.
The old snapshot has **not** been confirmed as the journal-portal submission.
The resubmission package no longer uses it: the highlighted PDF in
`paper/ieee-paper/review_artifacts/submission/` diffs against the portal-submitted
source, stored at `paper/ieee-paper/review_artifacts/baseline/submitted_manuscript_portal.zip`,
and is rebuilt by `bash paper/ieee-paper/rebuild_submission.sh`.
Anyone with the link can read the ZIP; it is not listed in Drive search.

Get the current clean PDF, annotated old/new comparison, generator, open-points
list, labels, identity manifest, and experiment results from **this GitHub
repository**; they are not duplicated in the supplement. To rerun the
134-image benchmark, obtain images matched to the committed labels separately:
the recorded rerun used 704×704 Roboflow identity copies, not full-resolution
originals. Those third-party images are **not** in the Drive ZIP while
redistribution terms remain unresolved. The model has a separate documented
Hugging Face download, and the IEEE template kit is not included. This review
supplement is not a submission-ready package.

## 1. What reproduces from this repo alone

### Synthetic robustness suite (zero external data)

The authored-circuit suite generates its own images and ground truth, so it needs
no dataset and no model. It backs **Table II** (synthetic leaderboard),
**Table III** (per-circuit at L4), and Fig. 5.

```bash
# Full report for the default strategy (scale_completion)
uv run python -m wire_detection.synthgt

# Table II — rank every join strategy on ground truth (join-only leaderboard)
uv run python -m wire_detection.synthgt --compare --seeds 8

# Table V — per-circuit, one strategy, 16 seeds
uv run python -m wire_detection.synthgt -s 16
```

SPICE columns require `ngspice` (set `NGSPICE_PATH`); without it, the join
scores still run. The error model is a deliberately-labelled placeholder (see the
CLI caveat and `docs/synthetic-eval-plan.md`).

### Score saved VLM responses (no model needed)

The Claude-VLM connectivity experiment is decoupled into "get responses" and
"score responses". The scoring phase runs against the committed responses and the
human-verified ground truth with no external data. This backs the **VLM row of
Table V** and the synthetic VLM control.

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

This reproduces the paired VLM−ours micro-F1 difference **+0.033, 95% CI
[−0.009, +0.078]**. The paper now reports the same comparison from our side
(ours − VLM = −0.033 [−0.078, +0.008]) with Holm-adjusted tests from
`revision2/stats_strata.py` (section 5.1); per image the VLM is better.

### Committed result artifacts

The final numbers are stored as JSON under `docs/research/experiments/`, so every
table/figure value can be inspected without re-running anything:

| Artifact | Contents |
|---|---|
| `join_micro_n31.json` | Join strategies, real detected wires, micro/macro + per-image counts (Table V core) |
| `cc_detected_micro_n31.json` | Connected-component baseline on identical detected wires (Table V) |
| `hough_micro_n31.json` | Hough + proximity baseline sweep (Table V) |
| `fair_join_comparison_n31.json` | Detected vs annotated wires, both with annotated boxes ("ours with annotated wires" row of Table V) |
| `detection_ceiling_n31.json` | Perfect-wire ceiling artifact |
| `bootstrap_ci_n31.json` | 95% bootstrap CIs + paired VLM−ours difference |
| `synthetic_leaderboard.json` | Table II synthetic leaderboard |
| `per_circuit_scale_completion_l4_n16.json` | Table III per-circuit at L4, 16 seeds |

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

### 134-image wire-detection benchmark (Table IV / Fig. 6)

The repository contains 134 paired wire and component label files in
`ground_truth/`. The reported rerun used staged **704×704 Roboflow identity
copies**, not full-resolution CGHD originals. Supply those matching images
explicitly to reproduce the reported coordinate system:

```bash
export WIRE_GT_IMAGES=/path/to/matching/704x704/identity/images
uv run python -m wire_detection.benchmark.expanded_benchmark
```

The benchmark rejects missing images or mismatched label sets instead of selecting
arbitrary Roboflow augmentations. The code does not check image dimensions or
pixel identity: the operator must verify that the images match the labels.
Original full-resolution scans have not been benchmarked with these annotations.
The command writes its 36-config ranking under
`output/benchmark_experiments/expanded_full_ranking/`. The 36-config sweep's
best (`best_candidate_v4`) is F1 0.9730. The deployed 12°/8 px dedup setting
used in every other experiment scores 0.973
(`docs/research/experiments/revision2/wire_rerun_deployed.json`). A subsequent **a16** parameter
change is recorded separately in
`docs/research/experiments/wire_a16_summary_jun2026.json` (F1
0.9755200226404415, TP 3447, FP 47, FN 77, redundant 49); instantiate `ExperimentConfig(**artifact["config"])` to replay
that **exact** configuration, rather than guessing its parameters. This
annotated-component wire benchmark does not run the YOLO detector.

### Real-image join eval + baselines (Table V), on detected wires

These detect wires from CGHD images using annotated component boxes, then run
each join strategy and score component-pair F1 against verified net ground truth.
They need images paired to the annotation coordinate system; the recorded
rerun used 704×704 identity copies, not original full-resolution scans. This
**conditional** join evaluation does not itself test autonomous component
detection. Run on the data host (`./.venv/bin/python`):

```bash
# Table V — join strategies (pass scale_completion explicitly: the default
# strategy list is degree_budget,graph_rescue,graph_scale,production and does
# NOT include the promoted scale_completion; use --strategies all for every one)
./.venv/bin/python -m wire_detection.benchmark.join_eval_real_f1 \
    --gt ground_truth/real_nets_verified.json \
    --strategies scale_completion,degree_budget,graph_scale,graph_rescue,production \
    --out docs/research/experiments/join_micro_n31.json

# Table V — connected-component baseline on the SAME detected wires
./.venv/bin/python -m wire_detection.benchmark.cc_baseline_detected \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/cc_detected_micro_n31.json

# Table V — Hough + proximity classical baseline (config sweep)
./.venv/bin/python -m wire_detection.benchmark.hough_baseline \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/hough_micro_n31.json

# Detected vs annotated wires (both with annotated component boxes)
./.venv/bin/python -m wire_detection.benchmark.detection_ceiling \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/fair_join_comparison_n31.json
```

The `join_eval_real_f1.py` command has now been executed on the data host
against 31 images: its JSON matched the committed `join_micro_n31.json` exactly,
including per-image counts. The script still selects a legacy Roboflow label by
first filename match; for these **31 specific images**, every selected label was
byte-identical to the corresponding committed identity label. Do not generalize
that match to other datasets or take it as detector-to-netlist validation.
The other commands above require separate execution and comparison; a listed
command by itself is not a reproduced result.

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
| **Table II**, Fig. 5 — Synthetic join leaderboard | `python -m wire_detection.synthgt --compare` | `synthetic_leaderboard.json` | none |
| **Table III** — Per-circuit at L4 (16 seeds) | `python -m wire_detection.synthgt -s 16` | `per_circuit_scale_completion_l4_n16.json` | none |
| **Table IV**, Fig. 6 — Wire detection (134 images) | `wire_detection/benchmark/expanded_benchmark.py` | `wire_a16_summary_jun2026.json`, `wire_threshold_full_ranking_jun2026.json`, `revision2/wire_rerun_deployed.json` | CGHD 704×704 copies |
| **Table V**, Fig. 7 — Human-verified join + baselines + VLM, paired tests | `join_eval_real_f1.py`, `cc_baseline_detected.py`, `hough_baseline.py`, `vlm_connectivity_eval.py`; tests by `revision2/stats_strata.py` | `join_micro_n31.json`, `cc_detected_micro_n31.json`, `hough_micro_n31.json`, `vlm_clean_rerun_n31.json`, `revision2/stats_strata_n31.json` | predictions need CGHD; tests do not |
| **Table VI** — Held-out benchmark (164) | `revision2/cghd_ref.py`, `cghd_eval.py`, `cghd_stats.py` | `revision2/cghd_ref_benchmark.json` | CGHD v12 for predictions; stats run from committed JSONs |
| Held-out scoring conventions, audit | `revision2/cghd_eval_ext.py`, `cghd_extended_scoring.py`, `cghd_audit_score.py` | `revision2/cghd_ref_extended_scoring.json`, `revision2/cghd_audit_results.json` | none for scoring |
| **Table VII** — Strata | `revision2/stats_strata.py`, `cghd_stats.py` | `revision2/stats_strata_n31.json`, `revision2/cghd_ref_benchmark.json` | none |
| **Fig. 8** — Controlled rescaling | `revision2/rescale_eval.py`, `plot_rescale.py` | `revision2/rescale_n31.json` | CGHD 704×704 copies |
| **Table VIII** — Edge-rule ablation | `join_eval_real_f1.py` variants | `revision_evidence/edge_ablation_results.{md,json}` | CGHD 704×704 copies |
| **Table IX** — Mechanism ablations (occlusion, guard, witness) | revision-round-3 runs (commit `b2e245f`); no standalone result JSON is committed, see `paper/ieee-paper/review_artifacts/REVIEW_CHANGES.md` | — | CGHD 704×704 copies |
| **Table X** — End to end with detector | `revision2/e2e_detected.py`, `stretch_check.py`, `make_e2e_md.py` | `revision2/e2e_detected_n31.json`, `stretch_check_n31.json` | CGHD originals (the v12 copy on claw) + 704 copies + model |
| **Table XI** — Per drafter | derived from `join_micro_n31.json` | `join_micro_n31.json` | none |

The wire benchmark and the real-image join command were rerun against staged
704×704 identity copies paired to the committed labels. They were not rerun on
full-resolution CGHD originals. Other rows have different dependencies and
must not be treated as independently rerun without their own output checks.

---

## 5. Revision-2 experiments

All scripts are in `wire_detection/benchmark/revision2/` and write under
`docs/research/experiments/revision2/`. None modifies pipeline code. The
committed results were produced on the data host `claw` (repo at `925a86f` or
later, `./.venv/bin/python` or `/home/claw/venv-ml/bin/python`, usually from a
scratch copy of the script with `PYTHONPATH` pointing at the repo). Summaries:
[`SUMMARY.md` → Revision 2](research/experiments/SUMMARY.md#revision-2-sept-2026).

Seeds: bootstrap `20260928`, permutation `20260929`, B = 10,000 image-level
resamples, 100k Monte Carlo permutations; Holm correction within each test type.

### Data and environment variables

| Variable | Default | Needed by | What it points at |
|---|---|---|---|
| `CGHD_ROOT` | `~/cghd_orig/cghd` | `cghd_*` scripts | CGHD **v12** from Zenodo ([10.5281/zenodo.10056817](https://doi.org/10.5281/zenodo.10056817)), unpacked so that `drafter_*/images/`, `drafter_*/instances/<stem>.json` (labelme polygons) and `drafter_*/segmentation/<stem>.jpg` (stroke maps) exist. 257 samples carry polygons and stroke maps. |
| `CGHD_ORIG` | `~/cghd_orig/cghd` | `e2e_detected.py`, `stretch_check.py` | Same CGHD originals (EXIF-corrected on load). |
| `WIRE_GT_IMAGES` | `/home/claw/workspace/ground_truth/labels_few_annot/images` | `e2e_detected.py`, `stretch_check.py`, `cghd_common.py`, `collect_per_image.py` | The 704×704 Roboflow identity copies that the committed labels refer to (`<stem>_jpg.jpg`). |
| `CIRCUIT_REPO` | `~/circuit-digitization` | `rescale_eval.py`, `size_dispersion.py` | Repo checkout. |
| `REV2_REPO` | repo containing the script | `collect_per_image.py` | Repo checkout. |

The CGHD v12 stroke maps and polygons are distributed separately from
CGHD-1152; the Zenodo record lists CC BY 4.0 while its bundled README states
CC BY-SA 3.0, so the derived reference nets in `ground_truth/cghd_ref/` are
released under CC BY-SA 4.0 (`ground_truth/LICENSE` §4). No CGHD images are
committed; audit overlays are regenerated locally.

### 5.1 Paired tests, strata and size dispersion (31 images) — no images needed

```bash
uv run python -m wire_detection.benchmark.revision2.stats_strata
# -> revision2/stats_strata_n31.json
```

Reads committed JSONs only. Expected: ours 0.890 (macro 0.901); ours − rescue
graph + completion +0.061 [+0.025, +0.100]; ours − VLM −0.033 [−0.078, +0.008]
(Holm p 0.12 bootstrap, 0.15 permutation, 0.030 Wilcoxon, W/T/L 7/11/13).
The per-image Hough counts it consumes (`per_image_inputs_n31.json`) come from
`collect_per_image.py`, which must run where the Roboflow labels match the
committed identity labels (31/31 on claw; a local `roboflow_test2/` may not):

```bash
REV2_REPO=$PWD PYTHONPATH=$PWD ./.venv/bin/python \
    wire_detection/benchmark/revision2/collect_per_image.py \
    --out docs/research/experiments/revision2/per_image_inputs_n31.json
```

### 5.2 Controlled rescaling (31 images, Fig. 8) — needs the 704×704 copies

```bash
PYTHONPATH=$PWD CIRCUIT_REPO=$PWD ./.venv/bin/python \
    wire_detection/benchmark/revision2/rescale_eval.py \
    --out docs/research/experiments/revision2/rescale_n31.json
PYTHONPATH=$PWD CIRCUIT_REPO=$PWD ./.venv/bin/python \
    wire_detection/benchmark/revision2/size_dispersion.py
uv run python wire_detection/benchmark/revision2/synth_mixed_size.py \
    --out docs/research/experiments/revision2/synth_mixed_size.json   # no external data
uv run python wire_detection/benchmark/revision2/plot_rescale.py      # figure
```

Expected (`scale_completion`): arm A (annotated wires) 0.855 / 0.895 / 0.886 /
0.890 / 0.888 / 0.887 / 0.887 at f = 0.35 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3; arm B
(re-extracted wires) 0.580 / 0.690 / 0.811 / 0.890 / 0.877 / 0.866 / 0.866. At
f = 1, arm B reproduces 418/37/66. Runs are deterministic.

### 5.3 End to end with the trained detector (31 images, Table X)

Needs the CGHD originals (`CGHD_ORIG`; the committed run used the v12 copy on claw), the 704×704 copies
(`WIRE_GT_IMAGES`) and `models/component_detection/yolo26m_obb_16class_aug.pt`.

```bash
PYTHONPATH=$PWD ./.venv/bin/python wire_detection/benchmark/revision2/stretch_check.py \
    --gt ground_truth/real_nets_verified.json \
    --out docs/research/experiments/revision2/stretch_check_n31.json
PYTHONPATH=$PWD ./.venv/bin/python wire_detection/benchmark/revision2/e2e_detected.py \
    --repo $PWD --out docs/research/experiments/revision2/e2e_detected_n31.json
python wire_detection/benchmark/revision2/make_e2e_md.py \
    --e2e docs/research/experiments/revision2/e2e_detected_n31.json \
    --stretch docs/research/experiments/revision2/stretch_check_n31.json \
    --old-current docs/research/experiments/revision2/e2e_old_script_current.json \
    --old-prefix docs/research/experiments/revision2/e2e_old_script_fe109ec.json \
    --out docs/research/experiments/revision2/e2e_detected_n31.md
```

Expected: detector on the original at conf 0.5 gives micro-F1 0.627
(316/208/168); the annotated-box oracle through the same path gives 418/37/66
(~95 s on claw CPU). The stretch check confirms the benchmark copies are
non-aspect-preserving resizes (median correlation 0.998; 16/31 stroke maps,
14/31 re-oriented). The earlier 0.247 is reproducible only with
`detected_boxes_eval.py` at `fe109ec` (hardcoded class-index table); the fixed
script gives 0.504 on the 704×704 copies.

### 5.4 Independent held-out benchmark (164 photographs, Table VI) — needs CGHD v12

Pipeline of scripts, in order (run from a scratch directory on the data host;
`out/` is scratch):

```bash
export CGHD_ROOT=/path/to/cghd_v12   # Zenodo 10056817, unpacked
R=wire_detection/benchmark/revision2
PY="env PYTHONPATH=$PWD ./.venv/bin/python"
$PY $R/cghd_ref.py --out out/cghd_ref_nets_v2.json            # reference nets (--variant v1|v2|v2_switch_closed)
$PY $R/cghd_transform_probe.py --out out/transform_probe.json  # dihedral k per benchmark copy
$PY $R/cghd_validate.py --ref out/cghd_ref_nets_v2.json --probe out/transform_probe.json \
    --out out/cghd_validate_v2.json                            # vs human nets on 17 overlaps
$PY $R/cghd_resolution.py --probe out/transform_probe.json --out out/cghd_resolution.json
$PY $R/cghd_eval.py --ref out/cghd_ref_nets_v2.json --out out/cghd_eval_photo.json
$PY $R/cghd_eval.py --ref out/cghd_ref_nets_v2.json --out out/cghd_eval_seg.json --input seg
$PY $R/cghd_input_ablation.py --probe out/transform_probe.json --out out/cghd_input_ablation.json
```

Copy the outputs into `docs/research/experiments/revision2/cghd_ref/` (the
reference itself is committed as `ground_truth/cghd_ref/cghd_ref_nets.json`),
then compute the statistics locally, no images needed:

```bash
uv run python -m wire_detection.benchmark.revision2.cghd_stats
# -> revision2/cghd_ref_benchmark.json
```

Expected: 179 of 257 images clean; reference vs human nets on the 17 overlaps
micro-F1 0.939; held-out clean set 164 images / 3874 pairs; ours 0.711
[0.671, 0.748] (P 0.766 / R 0.664); rescue graph + completion 0.659, CCL 0.594,
Hough 0.480; every Holm p = 0.0006. Strict held-out (155) 0.707; stroke-map
input 0.775. `cghd_viz.py` draws debug overlays for chosen stems (do not commit
them).

### 5.5 Extended scoring conventions

```bash
$PY $R/cghd_eval_ext.py --ref out/cghd_ref_nets_v2.json --stems out/ho164.txt \
    --out out/cghd_eval_ext_photo.json          # on the data host; pin-level nodes, all components
uv run python -m wire_detection.benchmark.revision2.cghd_extended_scoring   # local, numpy only
```

`ho164.txt` is the whitespace-separated list of the 164 held-out clean stems
(the `heldout_clean` subset of `cghd_ref_benchmark.json`). The rerun first
checks that it reproduces the primary table exactly (ours 0.7114). Expected on
164: extended components 0.709, switches closed 0.712, grounds merged 0.679,
all three 0.676; on the 139 images outside the wire benchmark, primary scoring
0.709. Ours leads every baseline in every variant.

### 5.6 Reference audit (40 random held-out draws)

```bash
$PY $R/cghd_audit_export.py --ref out/cghd_ref_nets_v2.json --out out/cghd_ref_audit  # stage (seed 20260928)
$PY $R/cghd_audit_overlays.py --audit out/cghd_ref_audit                              # context boxes
uv run python -m wire_detection.benchmark.revision2.cghd_audit_ui 8766                # verify in browser
uv run python -m wire_detection.benchmark.revision2.cghd_audit_score                  # score
```

The committed audit lives in `ground_truth/cghd_ref_audit/`
(`real_nets_working.json`, `timing_log.jsonl`, `model_check.json`,
`sample.json`); overlays are local only. Scoring needs no images. Expected
(`revision2/cghd_audit_results.json`): 37 of 40 scored (23 human-verified, 11
blind-model-matched, 3 model-adjudicated; 3 densest excluded); reference vs
final nets micro-F1 0.988 (P 1.000 / R 0.975), exact on 32; ours 0.764; median
human check 85 s.

### 5.7 Script index

| Script | Purpose |
|---|---|
| `stats_strata.py` | Paired bootstrap / permutation / Wilcoxon tests with Holm, complexity strata, size dispersion on the 31 images (committed JSONs only). |
| `collect_per_image.py` | Per-image Hough counts (all configs) and component-size stats for the 31 images. |
| `rescale_eval.py` | Resample the 31 images by 0.35–3×; join-only and full-pipeline arms. |
| `methods.py` | Method set for the scale experiments, incl. unclamped and fixed-px completion variants. |
| `size_dispersion.py` | Per-image component-size dispersion on the 31 images. |
| `synth_mixed_size.py` | Synthetic circuits with one component drawn 0.5×/2×/3× size. |
| `plot_rescale.py` | Fig. 8 from `rescale_n31.json`. |
| `stretch_check.py` | Verify the 704×704 copies are stretched, possibly re-oriented resizes of CGHD photos or stroke maps. |
| `e2e_detected.py` | End-to-end join with detector boxes run on the CGHD originals; loss decomposition. |
| `make_e2e_md.py` | Render `e2e_detected_n31.md` from the e2e JSONs. |
| `cghd_common.py` | Shared CGHD v12 loaders, frames, class mapping. |
| `cghd_ref.py` | Derive reference nets from CGHD v12 stroke maps + polygons. |
| `cghd_transform_probe.py` | Estimate the dihedral transform between CGHD originals and benchmark copies. |
| `cghd_validate.py` | Reference vs human nets on the 17 overlapping images. |
| `cghd_resolution.py` | Choose the photo input resolution from wire-level labels only. |
| `cghd_eval.py` | Frozen pipeline + baselines on the 257 CGHD samples (photo or stroke-map input). |
| `cghd_stats.py` | Held-out statistics and subsets from the stored predictions. |
| `cghd_input_ablation.py` | Input-modality ablation on the 17 overlaps. |
| `cghd_eval_ext.py` | Rerun storing pin-level nodes over all components, for extended scoring. |
| `cghd_extended_scoring.py` | Extended components, switches closed, grounds merged. |
| `cghd_audit_export.py` | Stage the seeded 40-image audit batch. |
| `cghd_audit_overlays.py` | Burn context boxes for unscored parts into audit overlays. |
| `cghd_audit_ui.py` | Serve the verification UI on the audit batch. |
| `cghd_audit_score.py` | Score the audit (reference and methods vs final nets, timing). |
| `cghd_viz.py` | Debug overlays of reference nets. |
