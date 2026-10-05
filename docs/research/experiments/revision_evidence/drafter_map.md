# Drafter Mapping for 31-Image Benchmark (IEEE Access R1-1 / R1-5)

> **Label correction, 2026-10-05.** Four images of the 31-image human-verified benchmark were corrected (plain crossings are not connections; C112, C242, C66, C15). Numbers in this file that depend on the 31-image nets predate the correction; the current values (e.g. ours 0.884, VLM 0.946, end to end 0.602, reference vs human 0.971) are in `docs/research/experiments/SUMMARY.md` (Revision 2) and the paper. Regenerated JSON next to this file is current.

## Source of truth (updated 2026-09-26)

**Current:** the published Kaggle CGHD-1152 v14 file index (8,139 paths, fetched with
page-token traversal), independently cross-checked against the v13 index. All 31
benchmark image basenames occur under exactly one `drafter_N/images/` path; the
4,157 image paths are identical in v13 and v14. See sibling
`drafter_map_n31_provenance.json` for exact paths and checks.

**Historical limitation (superseded):**

`/home/claw/.cache/kagglehub/datasets/johannesbayer/cghd1152/14.archive` — a **1.95 GB Kaggle
download of CGHD-1152 that was never extracted** and whose zip **central directory is missing**
(truncated mid-download; `unzip -l` fails with "End-of-central-directory signature not found").
No extracted `drafter_N/` directories existed in that local cache; however,
`docs/experiments/data/cghd_quality_sweep.json` already recorded all 4,157
published image paths and their drafter folders (including the formerly inferred 15).

The archive's local file headers (PK\x03\x04) were recovered by direct binary scan (central
directory not required for this). This surfaced **3,666 entries**, covering drafters
`-1, 0, 1, 10–18` in full, in that order. Zip members were stored in **lexicographic (string),
not numeric, order** (`drafter_1 < drafter_10 < drafter_11 < … < drafter_18 < drafter_19 <
drafter_2 < drafter_20 < …`), so the truncation cuts off cleanly right after `drafter_18` — the
next lexicographic entry (`drafter_19`) never arrived. Drafters `19, 2–9, 20–31` are **absent
from the archive on disk**, not skipped by the CGHD dataset itself.

## Key finding: drafters follow a fixed circuit-index block formula

For every one of the 10 standard drafters present in the archive (`1, 10–18`), the circuit
indices (the `C<n>` in filenames) form an exact, non-overlapping, contiguous block of 12:

```
drafter_N covers circuits C[(N-1)*12 + 1 .. N*12],  for N = 1..31
```

The **published v14 and v13 image-path indexes independently confirm all 31
standard drafters** (zero deviation, exactly 12 unique circuit indices in each
predicted range, and 96 image paths per drafter). The ten listed below were all
that the truncated local archive could confirm before the full index was fetched.
Those ten are N = 1, 10, 11, 12, 13, 14, 15, 16, 17, 18. This matches
`docs/datasets.md`'s documented "drafter_1–31: 96 each, standard 12×2×4 structure."
`drafter_0` and `drafter_-1` are excluded from the formula (documented outliers — `drafter_0`
uses a different D-index scheme (D1–D163+) and `drafter_-1` is the pre-numbering batch with
negative circuit IDs).

## Mapping method

- **31 of 31 images: directly matched in the published dataset file index** — each exact
  `C<n>_D<d>_P<p>.jpg` basename occurs under exactly one `drafter_N/images/` folder in
  the v14 index; the image-path set is identical in v13. Matching is restricted to
  `images/`, because `segmentation/` sometimes reuses the same basename.
- **Historical archive-only count:** 16 of 31 could be directly located in the
  truncated local archive; the other 15 were provisionally inferred by the block
  formula, a limitation now superseded by the complete published indexes.
- **All 4,157 image basenames are unique** within `*/images/`; all 31 mapping
  entries agree with the older repo artifact `docs/experiments/data/cghd_quality_sweep.json`.
  This establishes CGHD's designated drafter folder, not independently identified
  handwriting or byte-level identity of preprocessed benchmark copies.

The quality-sweep artifact records path-level drafter folders, but the flat
31-image mapping lives at `docs/research/experiments/drafter_map_n31.json`.
`wire_detection/benchmark/cross_drafter_test.py` only recovers the *drawing*
index (D1/D2) from filenames, not the CGHD drafter; its `classify_drafter()`
function name is misleading — it returns "D1"/"D2", not a drafter ID.

## Full mapping (31/31)

| Image | Drafter | Confidence |
|---|---|---|
| C103_D2_P1_jpg | drafter_9  | verified_upstream_index_v14 |
| C109_D2_P3_jpg | drafter_10 | verified_upstream_index_v14 |
| C10_D2_P3_jpg  | drafter_1  | verified_upstream_index_v14 |
| C111_D1_P1_jpg | drafter_10 | verified_upstream_index_v14 |
| C112_D1_P1_jpg | drafter_10 | verified_upstream_index_v14 |
| C113_D2_P3_jpg | drafter_10 | verified_upstream_index_v14 |
| C115_D2_P3_jpg | drafter_10 | verified_upstream_index_v14 |
| C134_D2_P2_jpg | drafter_12 | verified_upstream_index_v14 |
| C134_D2_P4_jpg | drafter_12 | verified_upstream_index_v14 |
| C137_D1_P2_jpg | drafter_12 | verified_upstream_index_v14 |
| C138_D1_P3_jpg | drafter_12 | verified_upstream_index_v14 |
| C15_D2_P2_jpg  | drafter_2  | verified_upstream_index_v14 |
| C19_D1_P2_jpg  | drafter_2  | verified_upstream_index_v14 |
| C20_D2_P2_jpg  | drafter_2  | verified_upstream_index_v14 |
| C21_D1_P3_jpg  | drafter_2  | verified_upstream_index_v14 |
| C22_D2_P3_jpg  | drafter_2  | verified_upstream_index_v14 |
| C242_D1_P1_jpg | drafter_21 | verified_upstream_index_v14 |
| C28_D1_P3_jpg  | drafter_3  | verified_upstream_index_v14 |
| C29_D2_P4_jpg  | drafter_3  | verified_upstream_index_v14 |
| C2_D2_P1_jpg   | drafter_1  | verified_upstream_index_v14 |
| C33_D2_P2_jpg  | drafter_3  | verified_upstream_index_v14 |
| C37_D2_P4_jpg  | drafter_4  | verified_upstream_index_v14 |
| C4_D2_P4_jpg   | drafter_1  | verified_upstream_index_v14 |
| C5_D1_P1_jpg   | drafter_1  | verified_upstream_index_v14 |
| C66_D2_P4_jpg  | drafter_6  | verified_upstream_index_v14 |
| C77_D2_P2_jpg  | drafter_7  | verified_upstream_index_v14 |
| C83_D2_P4_jpg  | drafter_7  | verified_upstream_index_v14 |
| C84_D2_P1_jpg  | drafter_7  | verified_upstream_index_v14 |
| C9_D1_P1_jpg   | drafter_1  | verified_upstream_index_v14 |
| C9_D1_P3_jpg   | drafter_1  | verified_upstream_index_v14 |
| C9_D2_P3_jpg   | drafter_1  | verified_upstream_index_v14 |

All 31 images mapped. None unmappable.

## Per-drafter cell sizes (out of 31)

| Drafter | n images | Provenance |
|---|---|---|
| drafter_1  | 7 | 7 verified in upstream index |
| drafter_2  | 5 | 5 verified in upstream index |
| drafter_10 | 5 | 5 verified in upstream index |
| drafter_12 | 4 | 4 verified in upstream index |
| drafter_3  | 3 | 3 verified in upstream index |
| drafter_7  | 3 | 3 verified in upstream index |
| drafter_4  | 1 | verified in upstream index |
| drafter_6  | 1 | verified in upstream index |
| drafter_9  | 1 | verified in upstream index |
| drafter_21 | 1 | verified in upstream index |

**Decision: a per-drafter breakdown is feasible for 4 cells** (drafter_1=7, drafter_2=5,
drafter_10=5, drafter_12=4), all ≥4, all filename-verified. The remaining six
cells each have n=1–3, too small individually to support per-drafter
performance claims; they can be pooled into an "other drafters" bucket if needed.

## Per-drafter join micro-F1 (scale_completion metric, from `join_micro_n31.json`)

Micro-F1 = aggregate TP/FP/FN across each drafter's images, then compute F1 (not an average of
per-image F1 scores). Macro-F1 (mean of per-image F1) shown alongside for comparison.

| Drafter | n | micro-F1 | macro-F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| drafter_1  | 7 | 0.933 | 0.907 | 56 | 6  | 2  |
| drafter_10 | 5 | 0.987 | 0.995 | 37 | 1  | 0  |
| drafter_2  | 5 | 0.854 | 0.874 | 85 | 14 | 15 |
| drafter_12 | 4 | 0.913 | 0.938 | 21 | 0  | 4  |
| drafter_3  | 3 | 0.872 | 0.870 | 58 | 9  | 8  |
| drafter_7  | 3 | 0.910 | 0.916 | 81 | 1  | 15 |
| drafter_21 | 1 | 0.931 | 0.931 | 27 | 4  | 0  |
| drafter_9  | 1 | 0.429 | 0.429 | 3  | 0  | 8  |
| drafter_6  | 1 | 0.771 | 0.771 | 27 | 2  | 14 |
| drafter_4  | 1 | 1.000 | 1.000 | 23 | 0  | 0  |

Overall (n=31) micro-F1 = 0.890, matching `join_micro_n31.json`'s reported `micro.scale_completion.f1`
exactly — confirms the grouping/aggregation logic is consistent with the file's own totals.

Across the 4 well-populated cells, micro-F1 ranges from **0.854 (drafter_2) to 0.987 (drafter_10)**
— a ~13-point spread, all comfortably above a floor that would suggest catastrophic
drafter-specific failure, but real enough to be worth reporting as evidence of cross-drafter
generalization variance rather than uniformity.

## Recommended framing for the rebuttal

1. Report the per-drafter table above for the 4 cells with n≥4, explicitly noting n per cell
   (reviewers will want the sample sizes alongside any F1 numbers this small).
2. Disclose that each of the 31 benchmark images matches exactly one unique
   `drafter_N/images/` path in the published CGHD-1152 v14 index; v13 has the
   same image-path set. This is corpus provenance, not an independently measured
   handwriting classification.
3. Keep the incomplete local archive only as historical context for the old
   16-direct/15-inferred count; do not repeat that count as current provenance.
