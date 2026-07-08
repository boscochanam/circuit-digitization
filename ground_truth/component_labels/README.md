# CGHD component annotations for the 134 benchmark images

**Licence: CC BY 4.0.** These are CGHD-1152's own component annotations, re-exported. They are
*not* our work. See `../LICENSE` section 3 for the full attribution and statement of modifications;
credit Thoma, Bayer and Li (DFKI, <https://doi.org/10.5281/zenodo.6385814>) if you redistribute.

## What this is

134 files, `<image>_jpg.txt`, one per benchmark image. 5233 component boxes. Each non-empty line:

```
<class> x1 y1 x2 y2 x3 y3 x4 y4
```

Corner coordinates of an oriented bounding box, normalised to `[0, 1]`. Classes index the 58-entry
list mirrored by `COMPONENT_TYPES` in `wire_detection/benchmark/`.

The pipeline uses these to **occlude** components before wire detection. Without occlusion,
component internals (text, symbols, internal wiring) generate hundreds of false wire detections —
this is the ablation reported in the paper.

## Why these particular copies

Roboflow emits several `.rf.<hash>` copies of each image, most geometrically augmented, and
**the filename does not say which is which** — it is an opaque content hash in every case. Measured
across this benchmark:

- all **216** augmented copies carry labels differing from the identity copy's;
- for **31 of 111** stems the identity copy is *not* the alphabetically first;
- **23** stems have more than one pixel-identical copy, whose labels agree to within 1 px
  (Roboflow float re-quantisation).

Only the identity copy — the one pixel-identical to the original CGHD photograph — is reproduced
here, chosen by pixel comparison and recorded in `identity_manifest.json` (`roboflow_file`,
`roboflow_split`, `boxes`, `sha256`). Picking an augmented copy silently yields labels in the wrong
coordinate space: the benchmark then reports `otsu_component` = 0.5854 instead of 0.7894, with no
error raised. `expanded_benchmark.py` now refuses to guess.

## Effect

With these committed, reproducing the benchmark needs **no Roboflow export at all** — only the
CGHD-1152 images:

```bash
WIRE_GT_IMAGES=/path/to/cghd/images \
uv run python -m wire_detection.benchmark.expanded_benchmark
```

Verified 2026-07-08 with `WIRE_HDC_BASE` pointed at a nonexistent path: 134/134 images loaded,
`a16` F1 = 0.9755 (`tp=3447 fp=47 fn=77`), `adaptive_gaussian_skeleton` 0.8452, `otsu_component`
0.7894, `triangle_skeleton` 0.7583 — every delta against
`../../docs/research/experiments/wire_threshold_full_ranking_jun2026.json` exactly 0.0000.
