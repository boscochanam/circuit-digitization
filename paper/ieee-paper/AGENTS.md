# IEEE Paper — Agent Instructions

> Current state, 2026-09-29: revised manuscript for IEEE Access **Access-2026-33821**, ready for
> upload. Numbers trace to `docs/research/experiments/SUMMARY.md` (section "Revision 2") and the
> JSONs under `docs/research/experiments/revision2/`. Open items:
> `review_artifacts/OPEN_POINTS.md`.

## Current state

- **Work line:** `main`. Records are frozen as tags (`audit/evidence-20260908`, `v1.0.0`,
  `v1.0.1`); see `BRANCHES.md`.
- **Sources (keep bodies in sync):** `paper-access.tex` (IEEE Access kit, the submission source)
  and `paper-build.tex` (IEEEtran, local `pdflatex`). Any body edit goes into both.
  `paper.tex` is a superseded draft; do not edit.
- **Title:** "From Hand-Drawn Schematics to Structural Circuit Netlists: A Deterministic Pipeline
  with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark". The output is a
  structural netlist; the pipeline reads no component values or device models, and simulation of
  real scans is not evaluated.
- **Submission package:** `review_artifacts/submission/` (manuscript-clean.pdf,
  manuscript-highlighted.pdf, highlight-change-index.pdf, response-to-reviewers.pdf,
  paper-access-overleaf.zip). Rebuild everything with `bash rebuild_submission.sh` (needs
  pdflatex, git, uv).
- **Highlight baseline:** the portal-submitted source,
  `review_artifacts/baseline/submitted_manuscript_portal.zip`. Not commit `33f5e3d`.
- **Response letter:** `review_artifacts/RESPONSE_TO_REVIEWERS.md` → PDF via
  `build-response-pdf.py`.

## Conventions

- Primary metric: component-pair **micro-F1** (pairs of electrical components R/C/L/D/Q/V/IC
  sharing a net, pooled over images); macro-F1 alongside.
- Connectivity is read from drawn wires only: terminals and supply symbols are wire ends;
  identically labeled supplies are not merged by label.
- Every join receives annotated component boxes and its own detected wires unless stated
  (end to end is the exception).
- Strategy names are descriptive in the paper, identifiers in code: `scale_completion` → "scale-
  relative graph + completion" (ours), `degree_budget` → "rescue graph + completion",
  `graph_scale` / `graph_rescue` → "... graph (base)", `production` → "radius union-find
  (legacy)".
- A CI that includes zero means "not significant", not "equivalent". Do not call ours and the VLM
  "statistically indistinguishable": the VLM is better per image (Wilcoxon Holm p = 0.030).

## Verified key numbers

- Human-verified benchmark (31 images): ours **0.890** (P 0.919 / R 0.864, macro 0.901,
  418/37/66). Rescue + completion 0.829, scale-relative base 0.816, rescue base 0.787, radius
  union-find 0.667, Hough 0.805, CCL 0.624. All margins significant after Holm. VLM (Claude Opus
  4.8) 0.923; ours − VLM −0.033 [−0.078, +0.008], not significant on micro-F1.
- Held-out benchmark (164 CGHD photographs, 24 of 25 drafters, reference nets from CGHD v12
  stroke maps + symbol polygons): ours **0.711** [0.671, 0.748]; beats every baseline (Holm
  p = 0.0006). Without the 25 wire-benchmark overlaps (139): 0.709. Reference vs human nets on
  17 overlaps: 0.939.
- Audit of 40 random held-out draws: 37 scored (23 human, 11 blind-model-matched, 3
  model-adjudicated; 3 densest excluded); reference micro-F1 0.988, no false pairs; median 85 s
  per human check.
- Extended scoring (164): extended components 0.709, switches closed 0.712, grounds merged
  0.679, all three 0.676; ours first in each.
- End to end with the trained detector (conf 0.5): **0.627**. The old 0.247 was a class-index
  mapping bug.
- Rescaling 0.35–3×: join with annotated wires within ±0.005 of native from 0.5× to 3×; −0.035
  at 0.35×.
- Wire extraction (134 images): F1 0.976 best variant, 0.973 deployed setting. Detector mAP@0.5
  89.0% (released `best.pt`; 88.5% is the non-distributed final epoch); crossover recall 70.7%.
- Synthetic L4: ours 0.95, radius union-find 0.36.
- Image provenance: 704×704 benchmark copies are non-aspect-preserving Roboflow resizes; 14/31
  re-oriented; 16/31 and 45/134 are CGHD stroke maps.

## Licences (see `ground_truth/LICENSE`)

Code and own annotations MIT; CGHD-1152-derived overlays and component labels CC BY 4.0; CGHD
v12-derived reference and audit nets CC BY-SA 4.0.

## Figures

- Concept diagrams: native TikZ `figures/{pipeline_overview,endpoint_graph,completion}_tikz.tex`.
- Data charts (matplotlib): `figures/{wire_benchmark,join_comparison,real_join_comparison,rescale_robustness}.pdf`.
- Graphical abstract: `generate_graphical_abstract.py` (660×295, under 45 KB).
- Pipeline examples (Fig. 2): C37 + C111 via `generate_pipeline_examples.py`; counts come from
  the generator's exact config, never from the benchmark tables.

## Remaining (author-only)

- Portal upload.
- Signatory of the response letter (currently Bosco Chanam on behalf of all authors) and
  coauthor consent to the revised manuscript.
- Author names, affiliations, funding and bios change only with written consent of all authors.
