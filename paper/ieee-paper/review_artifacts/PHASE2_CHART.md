# Phase 2(a): chart correction

Starting source: `8f4e18b`; A/B mean paper-access.tex/paper-build.tex in this directory's parent. Only stored JSON was loaded; no benchmark, scoring, detector or manuscript build was run. The chart generator renders existing values only.

| Config in `/home/claw/circuit-digitization/output/benchmark_experiments/expanded_full_ranking/<config>/summary.json` | Stored key/value | Old → new display | Result |
|---|---|---|---|
| adaptive_gaussian_skeleton | `global_f1=0.8452311293153891` | 0.928 → 0.845 | PASS |
| triangle_skeleton | `global_f1=0.7582635186595582` | 0.758 → 0.758; explicit skeleton label added | PASS for this configuration |

Both summaries contain 134 image records. `phase2_evidence/chart.json` records their full configuration dictionaries, original file SHA256s, output PDF SHA256 and mechanically extracted text. Configs use `extraction_mode=skeleton`; these are alternative benchmark configurations, not production parameter changes.

Gaussian source SHA256: `82dd0d399ef7afdfd519cd0760a4ff2091d28d9bef75380a8b37f7255f80c930`.
Triangle source SHA256: `28ab750e7671eb93ca03912a888658006f74fbef1925be7439515f5ac89755ee`.

Triangle disposition: retain the supported 0.758 skeleton result. Inspection of summary/ranking JSONs under the original checkout's `output/benchmark_experiments`, the supplied `notes/scratch` JSONs, and this worktree's `docs/research/experiments` recovered no Triangle 0.795 configuration. `expanded_full_ranking/full_ranking.md:32` independently labels triangle_skeleton 0.7583. This search does not prove that no other historical generation exists. The inherited REVIEW_CHANGES.md statement calling 0.795 corrected evidence is withdrawn; no claim that this bar is the best possible Triangle configuration is added. The older root AGENTS.md 0.795 assertion remains historical guidance without a recovered summary pointer.

Mechanical changes: corrected generator value/bar length; labeled Gaussian/Triangle skeleton extraction; regenerated only `figures/wire_benchmark.pdf`; appended identical configuration/value text to the caption in A:179/B:155. The shared PDF is consumed by both sources. All other chart values remain unchanged. The figure-hash row in REVIEW_CHANGES.md is the historical T1 preservation record, not a current-file hash.

Validation: PDF extraction contains 0.845 and 0.758 and no 0.928; both captions match exactly. No visual or final typesetting approval is inferred. Phase-1 whole-submission numerical FAIL is narrowed, not globally waived: other provenance qualifications remain.
