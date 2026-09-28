# Open points — IEEE Access resubmission 33821 (updated 2026-09-29, final)

Submission set: `review_artifacts/submission/` (clean + highlighted manuscript vs 33f5e3d, change index,
response PDF, Overleaf zip). Sources: `paper-access.tex` / `paper-build.tex` (bodies in sync).
Numbers: `REWRITE_SPEC_R2.md` → `docs/research/experiments/revision2/`.

## Before upload (author actions)
- [x] **Audit**: final, 37 of 40 random held-out draws (23 human-verified, 11 blind-model-matched, 3 model-adjudicated, 3 densest excluded). Reference F1 0.988, no false pairs; median 85 s per human check. Scored by `python -m wire_detection.benchmark.revision2.cghd_audit_score`.
- [x] **CGHD licence**: decided. CGHD-1152-derived labels CC BY 4.0; CGHD v12-derived reference nets and audit labels CC BY-SA 4.0 (ground_truth/LICENSE §4).
- [x] **Baseline**: the portal-submitted source is stored at `review_artifacts/baseline/submitted_manuscript_portal.zip`; the highlighted PDF diffs against it.
- [ ] **Signatory** of the response letter (currently Bosco Chanam on behalf of all authors) and coauthor
      consent to the revised manuscript.
- [x] **Overleaf**: not needed; local build uses the official IEEE Access kit.
- [ ] Portal upload.

## Resolved in this round
- Provisional end-to-end 0.247 was a class-index mapping bug; real end-to-end 0.627 (Sec. V-G).
- Benchmark image provenance (stretch, re-orientation, 16/31 and 45/134 stroke maps) disclosed (Sec. IV-A).
- Graphical abstract regenerated at 660×295, 44 KB (`generate_graphical_abstract.py`).
