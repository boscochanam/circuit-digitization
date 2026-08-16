# Drafter Mapping for 31-Image Benchmark (IEEE Access R1-1 / R1-5)

## Source of truth

`/home/claw/.cache/kagglehub/datasets/johannesbayer/cghd1152/14.archive` — a **1.95 GB Kaggle
download of CGHD-1152 that was never extracted** and whose zip **central directory is missing**
(truncated mid-download; `unzip -l` fails with "End-of-central-directory signature not found").
No extracted `drafter_N/` directories exist anywhere else on this machine.

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

Verified exactly (zero deviation, exactly 12 unique circuit indices, no entries outside the
predicted range) for N = 1, 10, 11, 12, 13, 14, 15, 16, 17, 18. This matches
`docs/datasets.md`'s documented "drafter_1–31: 96 each, standard 12×2×4 structure."
`drafter_0` and `drafter_-1` are excluded from the formula (documented outliers — `drafter_0`
uses a different D-index scheme (D1–D163+) and `drafter_-1` is the pre-numbering batch with
negative circuit IDs).

## Mapping method

- **16 of 31 images: directly verified** — their exact filename (`C<n>_D<d>_P<p>.jpg`) was found
  as a literal path inside the recovered archive listing under exactly one `drafter_N/`.
- **15 of 31 images: inferred by the block formula** — their circuit index falls in a drafter
  block that is *not physically present* in the truncated archive (drafters 2, 3, 4, 6, 7, 9, 21).
  Confidence is high given the formula's 10/10 perfect fit on observed data, but these are **not
  directly confirmed** by file evidence on this machine.

No file in the repo or workspace (CSV, manifest, split file, roboflow_test2) already encodes a
C-index → drafter mapping; `wire_detection/benchmark/cross_drafter_test.py` only recovers the
*drawing* index (D1/D2) from filenames, not the drafter, and its `classify_drafter()` function
name is misleading — it returns "D1"/"D2", not a CGHD drafter ID.

## Full mapping (31/31)

| Image | Drafter | Confidence |
|---|---|---|
| C103_D2_P1_jpg | drafter_9  | inferred_by_formula |
| C109_D2_P3_jpg | drafter_10 | verified_in_archive |
| C10_D2_P3_jpg  | drafter_1  | verified_in_archive |
| C111_D1_P1_jpg | drafter_10 | verified_in_archive |
| C112_D1_P1_jpg | drafter_10 | verified_in_archive |
| C113_D2_P3_jpg | drafter_10 | verified_in_archive |
| C115_D2_P3_jpg | drafter_10 | verified_in_archive |
| C134_D2_P2_jpg | drafter_12 | verified_in_archive |
| C134_D2_P4_jpg | drafter_12 | verified_in_archive |
| C137_D1_P2_jpg | drafter_12 | verified_in_archive |
| C138_D1_P3_jpg | drafter_12 | verified_in_archive |
| C15_D2_P2_jpg  | drafter_2  | inferred_by_formula |
| C19_D1_P2_jpg  | drafter_2  | inferred_by_formula |
| C20_D2_P2_jpg  | drafter_2  | inferred_by_formula |
| C21_D1_P3_jpg  | drafter_2  | inferred_by_formula |
| C22_D2_P3_jpg  | drafter_2  | inferred_by_formula |
| C242_D1_P1_jpg | drafter_21 | inferred_by_formula |
| C28_D1_P3_jpg  | drafter_3  | inferred_by_formula |
| C29_D2_P4_jpg  | drafter_3  | inferred_by_formula |
| C2_D2_P1_jpg   | drafter_1  | verified_in_archive |
| C33_D2_P2_jpg  | drafter_3  | inferred_by_formula |
| C37_D2_P4_jpg  | drafter_4  | inferred_by_formula |
| C4_D2_P4_jpg   | drafter_1  | verified_in_archive |
| C5_D1_P1_jpg   | drafter_1  | verified_in_archive |
| C66_D2_P4_jpg  | drafter_6  | inferred_by_formula |
| C77_D2_P2_jpg  | drafter_7  | inferred_by_formula |
| C83_D2_P4_jpg  | drafter_7  | inferred_by_formula |
| C84_D2_P1_jpg  | drafter_7  | inferred_by_formula |
| C9_D1_P1_jpg   | drafter_1  | verified_in_archive |
| C9_D1_P3_jpg   | drafter_1  | verified_in_archive |
| C9_D2_P3_jpg   | drafter_1  | verified_in_archive |

All 31 images mapped. None unmappable.

## Per-drafter cell sizes (out of 31)

| Drafter | n images | Confidence mix |
|---|---|---|
| drafter_1  | 7 | 7 verified |
| drafter_2  | 5 | 5 inferred |
| drafter_10 | 5 | 5 verified |
| drafter_12 | 4 | 4 verified |
| drafter_3  | 3 | 3 inferred |
| drafter_7  | 3 | 3 inferred |
| drafter_4  | 1 | inferred |
| drafter_6  | 1 | inferred |
| drafter_9  | 1 | inferred |
| drafter_21 | 1 | inferred |

**Decision: a per-drafter breakdown is feasible for 4 cells** (drafter_1=7, drafter_2=5,
drafter_10=5, drafter_12=4), all ≥4. Of those, **3 rest entirely on directly verified filename
matches** (drafter_1, drafter_10, drafter_12 — 16/16 verified images land there), so those three
are safe to report with full confidence. drafter_2 (n=5) is formula-inferred only — report it,
but flag the inference basis if a reviewer pushes on provenance. The remaining 6 drafters have
n=1–3, too small individually to support any per-drafter claim; they can be pooled into an
"other drafters" bucket if a residual comparison is wanted, but should not be reported cell-by-cell.

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
2. Disclose that drafter_1/10/12 assignments are directly verified against the CGHD archive's
   file listing, while drafter_2's is inferred from the dataset's documented 12-circuits-per-drafter
   block structure (itself corroborated by 10/10 other drafters with zero exceptions) because the
   local copy of the archive is truncated.
3. Cheapest full-recovery path: re-download CGHD-1152 from Kaggle
   (`kaggle datasets download -d johannesbayer/cghd1152`, ~4–5 GB unpacked) to replace the
   truncated cache at `/home/claw/.cache/kagglehub/datasets/johannesbayer/cghd1152/14.archive`,
   then match all 31 filenames directly — this would upgrade all 15 "inferred" entries to
   "verified" in under an hour and is the only way to fully close the provenance gap before
   camera-ready.
