# Open points — IEEE Access resubmission 33821 (updated 2026-10-05)

Submission set: `review_artifacts/submission/` (clean + highlighted manuscript vs the portal-submitted version, change index,
response PDF, Overleaf zip). Sources: `paper-access.tex` / `paper-build.tex` (bodies in sync).
Numbers: `REWRITE_SPEC_R2.md` → `docs/research/experiments/revision2/`.

## Before upload (author actions)
- [x] **Audit**: final, 37 of 40 random held-out draws, all 37 human-verified (3 densest excluded). Reference F1 0.999, no false pairs, exact on 36; median 77 s per check.
- [x] **Label correction (2026-10-05)**: plain-crossing rule applied; C112, C242, C66 (crossings joined) and C15 (555 GND/CV pins) corrected in `ground_truth/real_nets_verified.json` (previous nets kept in the entries). Every 31-image result recomputed: ours 0.884, VLM 0.946 (now significantly better), end to end 0.602, reference-vs-human 0.971. Paper, response, figures and docs updated. Scored by `python -m wire_detection.benchmark.revision2.cghd_audit_score`.
- [x] **CGHD licence**: decided. CGHD-1152-derived labels CC BY 4.0; CGHD v12-derived reference nets and audit labels CC BY-SA 4.0 (ground_truth/LICENSE §4).
- [x] **Baseline**: the portal-submitted source is stored at `review_artifacts/baseline/submitted_manuscript_portal.zip`; the highlighted PDF diffs against it.
- [ ] **Signatory** of the response letter (currently Bosco Chanam on behalf of all authors) and coauthor
      consent to the revised manuscript.
- [x] **Overleaf**: not needed; local build uses the official IEEE Access kit.
- [ ] Re-run the similarity check on the rebuilt `manuscript-clean.pdf`.
- [ ] Portal upload.

## Known gaps (optional)
- Mechanism and edge ablations (Tables 8, 9), annotated wires, crossover deletion and the reach sweep now come from the committed driver `wire_detection/benchmark/revision2/n31_arms.py`, which stores per-image predicted pairs (`docs/research/experiments/revision2/n31_arms.json`) and reproduces the earlier numbers exactly on the pre-correction nets.
- The photograph arm of the input ablation on the 17 overlaps (`cghd_input_ablation.json`, ours with annotated boxes at long side 1024) needs the CGHD originals and was not rescored; the paper's gap paragraph now uses the stored held-out predictions instead.
- Zenodo archive v1.0.1 predates the revision; mint a new release after acceptance if desired.

## Resolved in this round
- Provisional end-to-end 0.247 was a class-index mapping bug; real end-to-end 0.627 (Sec. V-G).
- Benchmark image provenance (stretch, re-orientation, 16/31 and 45/134 stroke maps) disclosed (Sec. IV-A).
- Graphical abstract regenerated at 660×295, 44 KB (`generate_graphical_abstract.py`).
