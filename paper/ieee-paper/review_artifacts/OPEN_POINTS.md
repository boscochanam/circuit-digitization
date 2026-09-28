# Open points — IEEE Access resubmission 33821 (updated 2026-09-29)

Submission set: `review_artifacts/submission/` (clean + highlighted manuscript vs 33f5e3d, change index,
response PDF, Overleaf zip). Sources: `paper-access.tex` / `paper-build.tex` (bodies in sync).
Numbers: `REWRITE_SPEC_R2.md` → `docs/research/experiments/revision2/`.

## Before upload (author actions)
- [ ] **40-image audit** of the held-out reference (`python -m wire_detection.benchmark.revision2.cghd_audit_ui`,
      http://127.0.0.1:8766). Then fill the `% TODO-AUDIT` sentence (Sec. V-D, both .tex) and the two
      `[AUDIT RESULT PENDING]` markers in `RESPONSE_TO_REVIEWERS.md`; rebuild PDFs + highlighted PDF.
- [ ] **CGHD licence**: Zenodo record 10056817 says CC BY 4.0; the README bundled in the archive says
      CC BY-SA 3.0. Decide the licence for `ground_truth/cghd_ref/` and `component_labels/` before release.
- [ ] **Baseline confirmation**: highlighted PDF diffs against 33f5e3d (July, 10 pp). Confirm this is the
      version the portal received.
- [ ] **Signatory** of the response letter (currently Bosco Chanam on behalf of all authors) and coauthor
      consent to the revised manuscript.
- [ ] **Overleaf render** of `paper-access-overleaf.zip` (local build: 13 pp, no blank pages).
- [ ] Portal upload.

## Resolved in this round
- Provisional end-to-end 0.247 was a class-index mapping bug; real end-to-end 0.627 (Sec. V-G).
- Benchmark image provenance (stretch, re-orientation, 16/31 and 45/134 stroke maps) disclosed (Sec. IV-A).
- Graphical abstract regenerated at 660×295, 44 KB (`generate_graphical_abstract.py`).
