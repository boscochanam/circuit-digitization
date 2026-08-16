# Otsu F1 discrepancy — resolved by re-running the benchmark

**Date:** 2026-08-16
**Command:** `/home/claw/venv-ml/bin/python /tmp/run_otsu_check.py` (standalone script,
imports `wire_detection.benchmark.expanded_benchmark` read-only — no repo files modified)

## What the script does
Reuses `expanded_benchmark.preload_all_images()` / `run_config()` verbatim — i.e. the
exact "corrected eval" harness described in AGENTS.md: 134 images, GT wire labels loaded
from `manually_verified_no_background_data`, HDC component labels loaded via
`find_exact_match()` (pixel-identical Roboflow version, not first-match), original
(non-augmented) images used for detection. This is the same eval generation that produced
the 0.9755 a16 number in AGENTS.md.

## Configs run
- `expanded_best_v4` — v4 baseline exactly as defined in `expanded_benchmark.py` `__main__`
  (anchor_endpoint_dist=12)
- `a16` — identical to v4 baseline except `anchor_endpoint_dist=16` (per AGENTS.md: "Only
  change from v4 baseline: anchor_endpoint_dist 12 → 16")
- All 4 Otsu-thresholding configs that exist in the harness (`experiment_harness.py`
  `wave4_configs()`, the exact same set `expanded_benchmark.py` runs by default):
  `otsu_component`, `otsu_skeleton`, `otsu_clahe_skeleton`, `otsu_skeleton_reconnect`

Grepped the whole file for `threshold_method="otsu"` — confirmed these 4 are the *only*
pure-Otsu configs anywhere in the harness (waves 1–8). No hidden/missed Otsu variant.

## Results

| Config | F1 | Precision | Recall | TP | FP | FN | Red |
|---|---|---|---|---|---|---|---|
| **a16** | **0.9755** | 0.9729 | 0.9781 | 3447 | 47 | 77 | 49 |
| expanded_best_v4 (v4 baseline) | 0.9730 | 0.9741 | 0.9719 | 3425 | 44 | 99 | 47 |
| **otsu_component** | **0.7894** | 0.7962 | 0.7826 | 2758 | 487 | 766 | 219 |
| otsu_skeleton | 0.7366 | 0.7868 | 0.6924 | 2440 | 519 | 1084 | 142 |
| otsu_skeleton_reconnect | 0.7295 | 0.7663 | 0.6961 | 2453 | 587 | 1071 | 161 |
| otsu_clahe_skeleton | 0.6949 | 0.6706 | 0.7211 | 2541 | 961 | 983 | 287 |

**Best Otsu variant: `otsu_component`, F1 = 0.7894 ≈ 0.789**

## Harness sanity check (a16 / v4 reproduction)
My a16 run reproduces AGENTS.md's row **exactly**: F1 0.9755, P 0.9729, R 0.9781, FP 47,
FN 77 — bit-for-bit match. v4 baseline also reproduces exactly: F1 0.9730, P 0.9741,
R 0.9719, FP 44, FN 99. This confirms my harness generation is identical to the one that
produced the AGENTS.md corrected-eval table — same data loading, same exact-match label
resolution, same eval code path.

## Verdict

**The paper's Table I value (F1 = 0.789) is correct. AGENTS.md's 0.828 is stale/wrong.**

Given the harness reproduces a16 and v4-baseline bit-for-bit, and the best of the *only*
four Otsu configs that exist in the code tops out at 0.789 (otsu_component), there is no
config in this eval generation that produces 0.828 for Otsu. 0.828 does not correspond to
any code path currently in `experiment_harness.py`.

No config-name ambiguity was found — there's exactly one "best" Otsu config
(`otsu_component`), analogous to how AGENTS.md names `adaptive_gaussian_skeleton` as
the best adaptive-Gaussian config. It just wasn't named in the AGENTS.md prose the way
adaptive-Gaussian's was.

Likely explanation: 0.828 in AGENTS.md was carried over from an older/uncorrected eval
generation (before the exact-match-label fix / before the current 134-image GT set was
finalized) and never re-verified when the corrected-eval table was written, while the
paper's 0.789 already reflects the current corrected eval.

**Recommendation:** Keep the paper's Table I row at **F1 = 0.789** (P = 0.796, R = 0.783
now independently confirmed). Fix AGENTS.md's OTSU line from 0.828 to **0.828 → 0.789**
to match the same corrected-eval generation as the a16/adaptive-Gaussian/Triangle numbers
in that table.
