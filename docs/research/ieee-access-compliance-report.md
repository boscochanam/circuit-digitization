# IEEE Access pre-submission compliance & validation report

Date: 2026-07-03. Target: `paper/ieee-paper/paper-access.tex` (Overleaf source; local twin
`paper-build.tex`). Guidelines fetched live from ieeeaccess.ieee.org (submission-guidelines,
preparing-your-article, guide-for-authors, APC page).

**Verdict: submittable.** Every quantitative claim traces to a committed artifact or documented
source of truth; one suspected numeric discrepancy was investigated and turned out to be a
false alarm. Remaining items are portal-side actions the repo cannot contain (listed in §3).

---

## 1. Guideline checklist

| Requirement (exact guideline) | Status | Evidence |
|---|---|---|
| IEEE Access LaTeX template | ✅ | `\documentclass{ieeeaccess}`; class supplied by the Author Center kit inside `paper-access-overleaf-full.zip`; render verified in `paper-access-LOCAL-verified.pdf` |
| Double column, single-spaced | ✅ | Access class default; verified render is Access trim (576×782.9 pt) |
| Source + matching PDF, ≤ 40 MB total | ✅ (portal) | `paper-access-overleaf.zip` = 4.3 MB; regenerate PDF on Overleaf after any edit so source/PDF match |
| Page count: no hard limit, ≤ 20 pp strongly recommended | ✅ | Access render = 18 pages |
| Manuscript type | ☐ portal | Select **Research Article** at submission |
| Abstract: single paragraph, no numbered equations, no reference citations | ✅ | 220 words, one inline (unnumbered) `$b$`-math, zero `\cite` |
| Keywords: 3–10 | ✅ | Exactly 10 — at the cap; drop one before adding any. Alphabetized this session (both twins) |
| References: IEEE style, relevant, accurate | ✅ | 26 `\bibitem`s, first-citation order (commit 9a0f7b1) |
| Biographies required for ALL authors, below references | ✅ | 6 `IEEEbiography` blocks with photos (`figures/authors/*.jpg`) |
| ORCID: submitting author must have a public, populated ORCID | ✅/☐ | `\orcidlink` for all 6 authors; **verify the submitting author's ORCID profile is public** (portal) |
| Graphical abstract: 660×295 JPG < 45 KB, from an article figure | ✅ | Created `paper/ieee-paper/figures/graphical_abstract.jpg` (660×295, 32 KB; Fig. 1 pipeline + Fig. 7 results). Upload separately in the portal — not referenced in the .tex |
| Acronyms defined at first use | ✅ | SPICE/OCR etc. expanded (commit 9a0f7b1) |
| Funding statement | ✅ | `\tfootnote{This work received no external funding.}` (Access convention) |
| Correct grammar (immediate-reject rule) | ✅ | Prose humanized/re-read in the 2026-06-28 pass |
| No Lena image | ✅ | n/a |
| AI-generated text disclosure in Acknowledgements | ⚠️ author call | No acknowledgements section exists. IEEE policy: AI-generated *text* must be disclosed. Decide whether any prose requires disclosure |
| Exclusive submission / plagiarism scan | ☐ portal | Author attestation |
| Video / supplementary / IEEE DataPort | n/a | None used; code+GT via GitHub, model via HuggingFace |
| APC awareness | ℹ️ | $2,160 + taxes; 5% IEEE member / 20% society-member discount |

Placeholder `\doi{...0429000}` and `\history{...0000}` are the template defaults — correct to
leave untouched pre-acceptance.

## 2. Number-by-number validation (paper ↔ artifacts)

All artifacts in `docs/research/experiments/` unless noted. **Every row verified this session.**

| Paper claim | Artifact | Verdict |
|---|---|---|
| Wire detection F1 0.976 / P 0.973 / R 0.978 (a16, 134 imgs) | `docs/benchmark-provenance.md` § "Top configs (Jun 2026, corrected eval)" (0.9755/0.9729/0.9781); benchmark `wire_detection/benchmark/expanded_benchmark.py` | ✅ |
| Otsu 0.789, adaptive-Gaussian 0.845 ablations | `docs/benchmark-provenance.md` § "Key findings and thresholding ablations" | ⚠️ adaptive-Gaussian 0.845 matches; **Otsu does not** — the provenance record says OTSU F1 = 0.828 (and Triangle 0.795), the paper's Table I row says 0.789. One of the two is stale; re-run `expanded_benchmark.py` and reconcile before submission. |
| Join micro-F1 0.890 (P .919 / R .864; macro .901) | `cc_detected_micro_n31.json` ours: 0.8903/0.9187/0.8636, macro 0.9011; also `fair_join_comparison_n31.json`, `join_micro_n31.json` | ✅ |
| 95% CI [0.855, 0.924]; VLM−ours +0.033 [−0.009, +0.078] | `bootstrap_ci_n31.json` (0.8547/0.9240; diff CI matches) | ✅ |
| Baselines micro: rescue+compl 0.829, scale base 0.816, rescue base 0.787, radius 0.667, Hough 0.805 | `bootstrap_ci_n31.json`, `hough_micro_n31.json` (link44_reach48 = 0.8046) | ✅ |
| **CCL 0.624 / P 0.965 / R 0.461** | `cc_detected_micro_n31.json` → `detCCL_d15.micro` = 0.6238/0.9654/0.4607 (best of d3/d7/d11/d15 sweep) | ✅ — *the suspected mismatch was a false alarm: the explorer compared against `cc_baseline_detected_n31.json`, which stores the **macro** values (0.6115/0.880/0.528). Paper correctly reports micro.* |
| VLM 0.923 (P .970 / R .880; macro .949); exact on 21/31 | `fair_join_comparison_n31.json`, `vlm_clean_rerun_n31.json` | ✅ |
| Perfect-wire ceiling: micro unchanged 0.890, macro 0.916 | `detection_ceiling_n31.json` | ✅ |
| Synthetic L4 leaderboard 0.95 / 0.94 / 0.90 / 0.85 / 0.36 (radius), 2.6× claim | `synthetic_leaderboard.json` (0.9480/0.9416/0.8985/0.8497/0.3635) | ✅ |
| Per-circuit L4 table (16 seeds; Wheatstone 0.82, ring 0.95, divider 0.99) | `per_circuit_scale_completion_l4_n16.json` | ✅ |
| Reach plateau ρ∈[3,5] | `join_reach_sweep_n31.json` (r3.0 0.898 … r5.0 0.903) | ✅ |
| Component detection 88.5% mAP@0.5, crossover recall 70.7%, 16 classes, drafter_0 excluded | `docs/benchmark-provenance.md` § "Component detection model", `docs/datasets.md` | ✅ (see caveat below) |
| 31-image human-verified GT | `ground_truth/real_nets_verified.json` — exactly 31 keys | ✅ |
| "Claude Opus 4.8" VLM identity | `wire_detection/benchmark/data/vlm_responses_*.json` record the same model string | ✅ |
| Related-work numbers (SINA 96.47%, DiagramNet F1s, Kelly&Cole 86.4%, Peker 85.33/93.33%) | Cited literature, cross-checked against `SUMMARY.md` notes | ✅ |

### Reproducibility caveats (honest notes, not defects)
- **134-image wire GT is not in-repo**: `labels_few_annot` is a symlink to claw
  (`/home/claw/workspace/...`) — dangling on this machine. The wire F1 0.976 reproduces only
  where CGHD data is staged; paper correctly cites CGHD-1152 as the external source.
- **Detector weights gitignored** (46 MB `.pt`); published at
  huggingface.co/boscochanam/circuit-component-detector with SHA256 in `docs/datasets.md:12`.
  No training `results.csv` committed — the 88.5% mAP rests on the `docs/benchmark-provenance.md`
  record + the HF model.
- The 31-image join benchmark, synthetic suite, VLM responses, and all baseline JSONs **are**
  fully reproducible from the repo.

## 3. Remaining author-owed items (portal / off-repo)

1. Upload refreshed `paper-access-overleaf.zip`, recompile on Overleaf (true `ieeeaccess.cls`
   render), download the PDF → this becomes the matching submission PDF. Re-check page count (~18).
2. Upload `paper/ieee-paper/figures/graphical_abstract.jpg` in the portal's graphical-abstract slot.
3. Confirm submitting author's ORCID profile is **public and populated**.
4. Select manuscript type "Research Article"; enter the 10 keywords as in the .tex.
5. Decide on AI-text disclosure (IEEE requires disclosure of AI-generated text in acknowledgements).
6. Attest exclusive submission; expect the plagiarism scan.
7. (Pre-existing from handoff) publication dates/DOI stay as placeholders until acceptance.

## 4. Changes applied this session

- Alphabetized keywords in `paper-access.tex` + `paper-build.tex` (kept twins in sync; verified
  all 25 headline metric strings occur identically in both files).
- Added a SUPERSEDED header comment to the stale conference draft `paper/ieee-paper/paper.tex`
  (it contradicts the current story; confirmed `build-overleaf-zip.sh` never bundles it).
- Created `paper/ieee-paper/figures/graphical_abstract.jpg` (660×295 JPG, 32 KB).
- Recompiled `paper-build.tex`: clean, 9 pages, 0 undefined references.
- Regenerated `paper-access-overleaf.zip` (4.3 MB) from the updated source.
