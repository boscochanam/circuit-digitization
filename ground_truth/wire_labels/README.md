# Ground-truth wire polylines (134 images)

The answer key for the wire-detection benchmark: Table I and Figure 3 of the paper, and every
number in `docs/benchmark-provenance.md`.

## What this is

134 `.txt` files, one per CGHD-1152 image, named `<image>_jpg.txt`. Each non-empty line is one
ground-truth wire segment, in YOLO oriented-bounding-box form:

```
0 x1 y1 x2 y2 x3 y3 x4 y4
```

Class `0` is the only class (`line`). The eight coordinates are the box corners, normalised to
`[0, 1]` against the source image's width and height. 3524 wire segments in total.

Parsed by `wire_detection/benchmark/reference_pipeline.py:load_ground_truth()`.

## Provenance and licence

These annotations are **original work by this repository's authors**, drawn over images from
CGHD-1152. They contain **no CGHD pixels** — only coordinates, and a filename in the CGHD naming
scheme. They are released under the repository's MIT licence, like `real_nets_verified.json`.

The **images** are not here. CGHD-1152 is CC BY 4.0 (Thoma, Bayer, Li; DFKI;
<https://doi.org/10.5281/zenodo.6385814>) and we do not redistribute the scans. See
`../LICENSE` and `../README.md`.

## Reproducing the benchmark

You need the CGHD scans and a Roboflow component-label export. Read **the Roboflow identity-copy
trap** in `../README.md` first — an export missing the identity copies produces silently wrong
numbers rather than an error.

```bash
WIRE_GT_IMAGES=/path/to/cghd/images \
WIRE_HDC_BASE=roboflow_test2 \
uv run python -m wire_detection.benchmark.expanded_benchmark
```

`WIRE_GT_WIRE_LABELS` defaults to this directory.

Verified 2026-07-08 on a clean run against
`../../docs/research/experiments/wire_threshold_full_ranking_jun2026.json`:

| Config | F1 | Precision | Recall |
|---|---|---|---|
| `a16` (the paper's configuration) | 0.9755 | 0.9729 | 0.9781 |
| `adaptive_gaussian_skeleton` | 0.8452 | 0.8723 | 0.8198 |
| `otsu_component` | 0.7894 | 0.7962 | 0.7826 |
| `triangle_skeleton` | 0.7583 | 0.8185 | 0.7063 |

a16 reproduces to `tp=3447 fp=47 fn=77`, exactly. Note that a16 is **not** one of the wave
configs enumerated by `expanded_benchmark.py`; it was run separately. Its frozen parameters are in
`../../docs/research/experiments/wire_a16_summary_jun2026.json` under `config`, and can be
replayed by constructing an `ExperimentConfig` from that dict.
