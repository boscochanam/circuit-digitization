# Human-verified net-level ground truth

This directory holds the connectivity benchmark introduced in the paper: 31 hand-drawn circuit
images from CGHD-1152 in which every electrical net was traced and confirmed by a human
annotator.

**Licensing is split.** The overlay images are CC BY 4.0, derived from CGHD-1152 (Thoma, Bayer,
and Li, DFKI — <https://doi.org/10.5281/zenodo.6385814>). The annotations are MIT, original to
this repository. Read [`LICENSE`](LICENSE) before redistributing anything here.

## Files

| Path | Keys | What it is |
|---|---|---|
| `real_nets_verified.json` | 31 | **The answer key.** Every real-image number in the paper is scored against this. |
| `real_nets_working.json` | 34 | What the verification UI edits. Superset of the above. |
| `net_gt_ui_meta.json` | 34 | Component bounding boxes and identities, normalized to `[0,1]`. |
| `net_gt_ui_overlays/*.png` | 34 | CGHD scans, grayscale, 4× upscaled, with GT wire polylines drawn on. **CC BY 4.0.** |
| `real_nets_vlm9.json` | 9 | Committed VLM responses, so the VLM row of Table III reproduces without API access. |
| `chris_ground_truth/*.zip` | — | Source component annotations (Ultralytics YOLO OBB export). |
| `local_eval/` | — | Gitignored. Symlinks to a local CGHD checkout; **absent from a clone.** |

## Why 34 overlays but 31 scored images

`real_nets_working.json` holds 34 images. `build_verified_gt.py` filters it down to the 31 that
are safe to score. An image is included iff (a) its source is human-verified, (b) it is not
marked `excluded`, and (c) it passes physical sanity — every electrical component appears in at
least one net, and in no more nets than it has terminals.

Three images are dropped:

| Image | Dropped by | Reason |
|---|---|---|
| `C167_D2_P1` | rule (a) | Bootstrap proposal from perfect GT wires; never human-verified. |
| `C105_D1_P4` | rule (c) | Human-verified, but `IC51` ends up isolated — no net contains it. |
| `C8_D1_P3` | rule (c) | Human-verified, but `transistor-BJT1` appears in 4 nets; a BJT has 3 terminals. |

The latter two are annotation slips caught by the sanity check, not disagreements about the
circuit. They are retained in the working file (and their overlays are retained here) so the
slips can be corrected later, but they are unsafe to score and no result in the paper uses them.

Regenerate the verified file at any time:

```bash
uv run python -m wire_detection.benchmark.build_verified_gt
```

It reports what it dropped and why.

## Getting the images

The overlays here exist only to drive the verification UI. Evaluation reads the original
CGHD-1152 JPEGs, which this repository does not vendor. Download them once (~4 GB):

```bash
curl -L -o ~/Downloads/cghd1152.zip \
  https://www.kaggle.com/api/v1/datasets/download/johannesbayer/cghd1152
unzip ~/Downloads/cghd1152.zip -d ./cghd1152/
```

Three inputs are resolved from the environment:

| Variable | Default | Holds | Survives a clone? |
|---|---|---|---|
| `WIRE_GT_IMAGES` | **none — must be set** | CGHD scans | ✗ not redistributed (CC BY source images) |
| `WIRE_GT_WIRE_LABELS` | `ground_truth/wire_labels/` | ground-truth wire polylines | ✓ **committed** (134 files) |
| `WIRE_HDC_BASE` | `roboflow_test2/` | ground-truth component labels | ✗ gitignored symlink |

`WIRE_GT_IMAGES` deliberately has **no default**. `ground_truth/local_eval/images` is the
*31-image net-GT set*, a different dataset; defaulting there would silently score 31 of 134 and
print a plausible-looking F1. `expanded_benchmark.py` now refuses to run without it, and warns
loudly if fewer than all 134 labelled images resolve.

### The Roboflow identity-copy trap

`WIRE_HDC_BASE` must point at an export that contains, for every image stem, the **identity**
`.rf.<hash>` copy — the one pixel-identical to the original CGHD scan. Roboflow exports also
contain *augmented* (rotated/flipped) copies whose labels live in a different coordinate space.
`find_exact_match()` picks the identity copy by pixel comparison; if it is absent it falls back to
`find_hdc_label_by_prefix()`, which returns an arbitrary — often augmented — label. Occlusion
polygons then land in the wrong place and every F1 silently collapses.

Observed, on an export missing the identity copies (1993 train files instead of 3986): **0 of 134
images matched exactly**, and the thresholding numbers came out `otsu_component` 0.5854,
`adaptive_gaussian_skeleton` 0.6825, `triangle_skeleton` 0.6197 — versus the published 0.7894 /
0.8452 / 0.7583. Nothing errored. To check your export before trusting a run:

```python
from wire_detection.benchmark import expanded_benchmark as eb
data = eb.preload_all_images()
exact = sum(1 for n, g, _, _ in data if eb.find_exact_match(n, g))
print(f"{exact}/{len(data)} exact matches")   # must be 134/134
```

Mind the filename convention. The scripts build image paths as `f"{name}_jpg.jpg"`
(`build_net_gt.py:54`, `detection_ceiling.py:64`), where `name` is a JSON key with its trailing
`_jpg` stripped — so key `C84_D2_P1_jpg` resolves to the file `C84_D2_P1_jpg.jpg`. That doubled
suffix is an artifact of a Roboflow export, not CGHD's own naming. If your CGHD checkout ships
`C84_D2_P1.jpg`, build a symlink farm first:

```bash
mkdir -p local_eval/images
python3 - <<'PY'
import json, pathlib
CGHD = pathlib.Path("./cghd1152/images")   # adjust to your checkout
out  = pathlib.Path("ground_truth/local_eval/images"); out.mkdir(parents=True, exist_ok=True)
for key in json.load(open("ground_truth/real_nets_verified.json")):
    name = key[:-4]                         # C84_D2_P1_jpg -> C84_D2_P1
    src  = CGHD / f"{name}.jpg"
    if not src.exists():
        print(f"MISSING {src}"); continue
    (out / f"{name}_jpg.jpg").symlink_to(src.resolve())
PY
```

Then:

```bash
WIRE_GT_IMAGES=ground_truth/local_eval/images \
WIRE_HDC_BASE=roboflow_test2 \
uv run python -m wire_detection.benchmark.detection_ceiling --perfect-gt-skip
```

The snippet above is written against the naming the scripts require; it has not been exercised
against a fresh CGHD download, so check the `MISSING` lines before trusting the result. Wire
labels (`WIRE_GT_WIRE_LABELS`) and component labels (`WIRE_HDC_BASE`) must be staged separately;
`--perfect-gt-skip` avoids needing the wire labels.

See [`../docs/reproducing-the-paper.md`](../docs/reproducing-the-paper.md) for the full
walkthrough.
