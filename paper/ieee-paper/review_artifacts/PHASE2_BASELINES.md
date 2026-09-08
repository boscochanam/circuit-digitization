# Phase 2(b): candidate manuscript diff inventory

This is a file/content inventory only. It does not identify what IEEE reviewed. A candidate's filename, date, ancestry or similarity is not submission-record evidence. No baseline is selected for highlighting.

Current sources are pinned at `02da5e6` (phase-2 chart fix); later phase-2 commits add reports only. Fork parent is `9bbe9e9`, distinct from fork tip `10c1b92`. No merge/rebase was performed. Full SHA256s, byte sizes and exact origins are in `phase2_evidence/baselines/manifest.json`.

| Candidate / representation | SHA256 |
|---|---|
| August-25 manuscript PDF, supplied review-materials directory | `b9bd9bb9427761d302774a33e7c8b107caf3db3882b8880cc7468ea620317c6b` |
| Fork parent A | `424bf8b487f8a547e9f7d4555ca5af4883fceeb9c8cfc433065497c7c238100e` |
| Fork parent B | `db4a0f80446185179ff91ff9694e082bd65497912647b6045a479574db43218f` |
| Current A | `9eef5e0f38bcb4b141c321b9c715165a9450b953fc64bf21bed90b03daf76485` |
| Current B | `511c463ea4452234e9bda7a69f0387eef83edea4f2ed72a3b2c167a63523e753` |
| Existing tracked worktree B PDF; not regenerated from current sources | `f5dee2131f8fa3d9d8adee5439b27cb5d674edd37dfd4bb745440bf031ffcd71` |
| Separate `context/00_original_paper/paper-build-original.pdf` candidate | `342be819e81d78ca2efa14065016e265418510660b321d0f38748533c38c3bb4` |

The three PDFs differ bytewise. The `00_original_paper` A/B source hashes also differ from both fork-parent and current sources; see manifest. The evidence-pack README's description of that snapshot is recorded as provenance only, not adopted as a reviewed-baseline conclusion.

## Diffs and representation limits

All files below are under `phase2_evidence/baselines/` and reproducible with the adjacent `inventory_baselines.py` (read inputs, extract existing PDF text, write local reports only).

| Comparison | Artifact | Raw diff inventory |
|---|---|---|
| Fork parent → current A | `parent-to-current-access.diff` | 14 hunks; 111 removed / 147 added source lines |
| Fork parent → current B | `parent-to-current-build.diff` | 15 hunks; 114 removed / 171 added source lines |
| August PDF extraction → fork parent B TeX | `august-to-parent-build.cross-format.diff` | 1 hunk; 1415 removed / 425 added lines; **cross-format discovery only** |
| August PDF extraction → current B TeX | `august-to-current-build.cross-format.diff` | 1 hunk; 1414 removed / 481 added lines; **cross-format discovery only** |
| August PDF → existing worktree PDF, extracted text | `august-to-existing-current-pdf.diff` | 30 hunks; 452 removed / 240 added text lines; existing PDF is not current-source proof |

No August-25 TeX source is present in the supplied review-materials directory, and the fork parent tracks no `paper-build.pdf`. Consequently, the two cross-format diffs intentionally preserve raw TeX and PDF reading-order text; their line totals are dominated by format, wrapping, page headers, mathematical extraction and figure text. They are not semantic edit counts, rendered comparisons, highlight maps or evidence of a matching source/PDF pair. No source-to-PDF equivalence is asserted. No manuscript build was run to manufacture a missing counterpart.

## Concrete content observations

August anchors below refer to stored `august25-extracted.txt` (default pdftotext reading order); parent/current anchors refer to B TeX at their pinned commits.

| Content | August 25 | Fork parent | Current |
|---|---|---|---|
| Title/product scope | Extracted title: SPICE Netlists; :15 explicitly says structural SPICE-format, external values | B:30 title SPICE Netlists; B:44 abstract says SPICE netlist | B:28 Structural Circuit Netlists; B:42 metric/export limits |
| VLM interpretation | :32 and :69 say statistically indistinguishable | B:44,73 same phrase | B:42,70 and `sec:vlm_results` explicitly reject equivalence and cost superiority |
| Pipeline example counts | :135 left 35 wires/7 nets, right 11 wires/4 nets | B:63 left 36/12, right 12/4 | B:60 left 35/7, right 11/4 |
| Completion description | :335 optimization and :538 short-prevention caption | B:160 constrained-optimization paragraph and B:167 caption | B:122–128 clamped reach, slot/dummy assignment and post-assignment guard |
| Wire chart | :556 Gaussian 0.928, :558 Triangle 0.758 | Shared graphic referenced by parent TeX; parent/current source diff alone does not compare graphic interiors | B:155 caption specifies skeleton 0.845/0.758; corrected shared PDF hash in chart ledger |

The example-count match between August and current does not make either a confirmed reviewed source. Likewise, the fork parent is useful provenance for the fork patch, not a substitute for a submitted-source record.

**HUMAN-ONLY — reviewed-baseline identity:** Bosco or an authorized submission-account holder must supply/confirm the actual submitted artifact and source correspondence from the submission record, with hashes. Why: local file comparisons cannot establish which artifact the journal received or used. Until then, baseline-dependent highlighting and review-change completeness remain unverified.
