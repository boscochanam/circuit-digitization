# Component detector — training artifacts

Training logs for the YOLO26M-OBB component detector, plus the 61 → 16 class merge map. This
directory is the primary in-repo evidence for the detector numbers in the IEEE Access manuscript,
and it exists to fix a specific confusion: **the released checkpoint is not the final epoch.**

Companion prose: [`docs/benchmark-provenance.md`](../../../benchmark-provenance.md).

## Contents

```
detector/
  baseline_16class_noaug/
    results.csv
    run_metadata.json
  augmentations_16class_yolo26m/          <- the shipped model
    results.csv
    run_metadata.json
  augmentations_weights_16class_yolo26m/
    results.csv
    run_metadata.json
  class_map.json
  README.md
```

## Provenance

Training ran on a remote host. Every path inside `run_metadata.json` is rooted at
`/home/bflcv/Projects/Components/`, which exists on neither machine reachable from this repo.
The CSV and JSON files here were synced to `/home/bosco/Projects/Components/` and are byte-identical
(sha256) to the copies on host `claw`. They were copied into this directory unmodified; the sha256
of each file here matches its source.

| File | sha256 |
|---|---|
| `baseline_16class_noaug/results.csv` | `ff928b74f6f9b3f9673f561b085f9cbe208ae5e6ecd94b796200e91759dbffac` |
| `baseline_16class_noaug/run_metadata.json` | `07110b7226ec9163038faf825e73c185251be7fddb6d6d80a6db8be3bcbf8152` |
| `augmentations_16class_yolo26m/results.csv` | `4fec8ff3f5e587a1c3f8fd58a7c490740e74e2004c7d5ada5d95db8bf372971d` |
| `augmentations_16class_yolo26m/run_metadata.json` | `2d2383bb837596e5871ca4f8c3ddcda7686c82ce1fcd3ff28cc7efd79350db1b` |
| `augmentations_weights_16class_yolo26m/results.csv` | `9e96dc3a327dd2e93e3e3176d11f58664a0615df92f5c580ed194938e61eec24` |
| `augmentations_weights_16class_yolo26m/run_metadata.json` | `2af2113f0c23bf92eafb72d3a156c30ff0349d4dd8c12d21d3f45be4194719df` |

**What is missing.** The dataset YAML (`data/cghd_16class.yaml`) and the 468 validation images are
on neither reachable machine. Per-class metrics therefore **cannot currently be regenerated**. Every
claim below is derived from the committed logs, from metrics embedded in the checkpoint, or from
arithmetic over both. Nothing below required re-running validation.

Shared training setup, read off `run_metadata.json`: 2,652 train / 468 val images, 85/15 random
split, `drafter_0` excluded, imgsz 1024, AdamW, `lr0=0.001`, `cos_lr=true`, seed 42, RTX 6000 Ada.

## The shipped model

`augmentations_16class_yolo26m/weights/best.pt`, sha256
`d700b33f90191968af9f7f2798fff5e90a3f1ea473b811adc241bc570987264d`, distributed via
`scripts/download_model.py` (HuggingFace: `boscochanam/circuit-component-detector`).

Weights are **not** committed here — too large. This directory holds the logs only.

## Metric provenance: `best.pt` is epoch 121, not epoch 200

This is the point of the directory.

- `best.pt` embeds `train_metrics` = P **0.95778**, R **0.88621**, mAP50 **0.88977**,
  mAP50-95 **0.78510**.
- Ultralytics writes `best.pt` at maximum *fitness*, defined as `0.1*mAP50 + 0.9*mAP50-95`. Over all
  220 rows of `augmentations_16class_yolo26m/results.csv` that maximum falls at **epoch 121**
  (fitness 0.79557), and the epoch-121 row reproduces all four embedded numbers exactly.
- The **final** epoch (200) is a different row: P 95.62, R 88.63, mAP50 88.47, mAP50-95 78.31
  (fitness 0.79321). That is `last.pt`, which is **not** distributed.

**Therefore the released checkpoint scores mAP@0.5 = 89.0%, not 88.5%.** The 88.5% figure that
circulated is `last.pt`'s.

## Which run owns the per-class recall table

`RUN_RESULTS.md` (in the training repo) carries a 16-row per-class table, each value rounded to one
decimal place. It was not labelled with a run or an epoch. The attribution can be settled by
arithmetic alone, without the validation set.

Ultralytics computes the overall `mAP50` and `R` as **unweighted means over the 16 classes**. The
per-class table averages to mean R = **88.625** and mean mAP50 = **89.025**. A mean of 16 values each
rounded to 1 dp is accurate to ±0.05, so the source epoch must have R ∈ [88.575, 88.675] and
mAP50 ∈ [88.975, 89.075].

| Candidate | R | mAP50 | Verdict |
|---|---|---|---|
| Run 2, epoch 121 (`best.pt`) | 88.621 | 88.977 | **Inside both windows.** |
| Run 2, epoch 200 (`last.pt`) | 88.628 | 88.468 | mAP50 off by 0.56 — eleven times the bound. Excluded. |
| Run 2, any other epoch | — | — | None satisfies both. Epoch 58 has mAP50 89.073 but R 86.195. |
| Run 3, all 188 epochs | — | max 88.783 | Its highest mAP50 anywhere is below the 88.975 floor. Excluded outright. |

Epoch 121 of Run 2 is the **only** epoch in either augmented run that satisfies both constraints.

**Consequence.** The per-class table — including `crossover = 70.7% recall` — belongs to Run 2's
`best.pt`. `RUN_RESULTS.md`'s "Key Learning #4", which claims class weighting lifted crossover
recall from 67% to 70.7%, is **wrong**: 70.7% is Run 2's number, produced *without* class weighting.
Run 3's own metadata already records `crossover: recall 0.707` as the *targeted* weak class, i.e. as
its input, not its result.

### The per-class table

Reproduced here because the manuscript cites two of its cells (`operational_amplifier` 100%,
`crossover` 70.7%) and the training repo is not public. Attributed above to Run 2, `best.pt`,
epoch 121. Values as recorded, one decimal place.

| Class | Recall | mAP50 | | Class | Recall | mAP50 |
|---|---|---|---|---|---|---|
| `operational_amplifier` | 100.0 | 99.4 | | `other` | 90.4 | 93.4 |
| `inductor` | 94.9 | 94.7 | | `gnd` | 89.4 | 88.9 |
| `voltage_source` | 92.8 | 95.3 | | `text` | 85.3 | 85.2 |
| `capacitor` | 92.2 | 92.7 | | `junction` | 84.9 | 84.3 |
| `transistor` | 92.1 | 94.8 | | `terminal` | 84.2 | 84.9 |
| `resistor` | 91.7 | 93.2 | | `switch` | 83.4 | 78.3 |
| `diode` | 91.6 | 93.1 | | `vss` | 83.1 | 85.9 |
| `integrated_circuit` | 91.3 | 91.0 | | `crossover` | **70.7** | **69.3** |

Means: recall 88.625, mAP50 89.025 — the two figures the attribution argument above rests on.
Note `other` scores 90.4% recall, but that is recall on the *catch-all bin*, not on any device type
it contains.

## Results

Both the best-fitness epoch and the final epoch are given for each run, computed from the CSVs in
this directory. Fitness = `0.1*mAP50 + 0.9*mAP50-95`. Values are percentages.

| Run | Row | Epoch | P | R | mAP50 | mAP50-95 | Fitness |
|---|---|---|---|---|---|---|---|
| 1 — `baseline_16class_noaug` | best surviving | 20 | 91.18 | 83.53 | 85.14 | 72.41 | 0.73678 |
| 1 — `baseline_16class_noaug` | final logged | 177 | 91.42 | 83.63 | 82.39 | 70.19 | 0.71405 |
| **2 — `augmentations_16class_yolo26m`** | **best fitness → `best.pt`** | **121** | **95.78** | **88.62** | **88.98** | **78.51** | **0.79557** |
| 2 — `augmentations_16class_yolo26m` | final → `last.pt` | 200 | 95.62 | 88.63 | 88.47 | 78.31 | 0.79321 |
| 3 — `augmentations_weights_16class_yolo26m` | best fitness | 130 | 94.81 | 88.65 | 88.67 | 78.38 | 0.79411 |
| 3 — `augmentations_weights_16class_yolo26m` | final | 188 | 95.47 | 88.70 | 88.33 | 78.05 | 0.79080 |

Run 1's "best surviving" row is qualified — see the next section. Run 3 stopped at epoch 188 on
`patience=50` and never beat Run 2 on any metric; class weighting did not help.

Run 2's best-fitness row at full precision, for checking against the checkpoint:
P `0.95778`, R `0.88621`, mAP50 `0.88977`, mAP50-95 `0.78510`.

## `results.csv` integrity

| Run | Rows | Max epoch | Duplicated | Missing | State |
|---|---|---|---|---|---|
| `baseline_16class_noaug` | 126 | 177 | 127, 128 | 53 rows | **Not reconstructible** |
| `augmentations_16class_yolo26m` | 220 | 200 | 152–171 (20 rows) | none | Usable; resumed |
| `augmentations_weights_16class_yolo26m` | 188 | 188 | none | none | Clean, monotonic |

**Run 2.** 220 rows for 200 epochs: epochs 152–171 each appear twice. The run was resumed —
`run_metadata.json` has `"resume": true` and `"model": ".../weights/epoch150.pt"`. Epoch 121 appears
exactly once and precedes the resume point, so the `best.pt` attribution is unambiguous.

**Run 3.** 188 rows, max epoch 188, no duplicates, epoch column monotonic. Clean.

**Run 1.** 126 rows but the epoch column reaches 177: **53 epoch rows are absent from the log**, and
epochs 127–128 are duplicated. This run was also resumed (`"model": ".../weights/epoch125.pt"`), and
the surviving rows appear to be a partial reassembly. The best *surviving* row is epoch 20
(mAP50 85.14, mAP50-95 72.41, P 91.18, R 83.53), but the true best-fitness epoch may lie in one of
the missing rows. `RUN_RESULTS.md` reports 85.0 / 72.3 / 91.1 / 83.4 for this run — about 0.08–0.14
below the best surviving row on all four metrics, consistent with a row that is gone.

**The baseline log is not fully reconstructible.** No number in the paper depends on it.

## Comparisons the paper deliberately does not cite

Two claims from the training notes are confounded and are omitted from the manuscript.

- **"Class merging is critical (61 → 16, ~50% → 85% mAP)."** The ~50% figure comes from a
  YOLO26L / 150-epoch / batch-5 run; the 85% figure from a YOLO26M / 200-epoch / batch-17 run. Model
  size, schedule length and batch size all changed alongside the class count. The merge may well
  help — this comparison cannot show by how much.
- **"M outperforms L."** That compares YOLO26L *without* augmentation against YOLO26M *with*
  augmentation. There is no L + augmentation run. Two variables changed.

The augmentation effect (Run 1 vs Run 2) is a cleaner comparison — same model, same schedule, same
batch — but Run 1's log is incomplete (above), so it is reported as a log-derived observation, not
a measured ablation.

## Class merge (61 → 16)

Extracted from `scripts/prepare_cghd_11class.py` in the training repo. The filename says `11class`;
the script emits **16**. Verified: `len(CLASS_MAP) == 61`, `len(CLASS_NAMES) == 16`, and the 16
target bins partition all 61 originals. Exact mapping: [`class_map.json`](class_map.json).

| Kind | Count | Classes |
|---|---|---|
| True merges of electrically-equivalent variants | 8 | `resistor` (3), `capacitor` (3), `diode` (4), `transistor` (3), `inductor` (3), `voltage_source` (3), `integrated_circuit` (3), `operational_amplifier` (2) |
| Pass-through (1 → 1) | 7 | `terminal`, `crossover`, `switch`, `text`, `junction`, `gnd`, `vss` |
| Catch-all | 1 | `other` — absorbs **30** of the 61 originals |

Target bins: 8 + 7 + 1 = 16. Originals absorbed: 24 + 7 + 30 = 61.

**`other` absorbs 30 classes**, among them `transformer`, `thyristor`, `triac`, `relay`,
`optocoupler`, `diac`, `crystal`, `speaker`, `fuse`, `motor`, `lamp`, `antenna`, `varistor`, the
logic gates (`and`, `or`, `not`, `nand`, `nor`, `xor`) and `unknown`. **The detector does not
discriminate among them.** A detection labelled `other` carries no information beyond "a component
that is not one of the other fifteen." Any downstream consumer needing, say, transformers must
re-classify the `other` boxes itself.

## Reproducing the numbers on this page

Everything in the results and integrity tables comes from the committed CSVs and requires only the
standard library:

```python
import csv
rows = list(csv.DictReader(open("augmentations_16class_yolo26m/results.csv")))
fit = lambda r: 0.1 * float(r["metrics/mAP50(B)"]) + 0.9 * float(r["metrics/mAP50-95(B)"])
best = max(rows, key=fit)          # epoch 121
last = max(rows, key=lambda r: int(r["epoch"]))  # epoch 200
```

The per-class attribution argument additionally uses the per-class table, reproduced above from the
training repo's `RUN_RESULTS.md`. Its two column means (88.625, 89.025) are what pin the table to
epoch 121; both are recomputable from the table as printed.
