# Deep validation task

You are the independent validator for the circuit-digitization repository. Work in this dedicated workspace only: `/home/claw/circuit-digitization-validation-20260907/repo`. Do not modify `/home/claw/circuit-digitization`, do not push or comment on GitHub, do not run the email script (`docs/experiments/send_pranavesh_audit.py`).

Phase 1 first: give your own original assessment of what Pranavesh did, what is correct/broken/stale, and where you disagree with the existing Claude plan — before filling any template. Phase 2: then produce the structured notes below.

Your deliverable is not a generic summary. Make evidence-linked notes in:
`/home/claw/circuit-digitization-validation-20260907/notes/VALIDATION_NOTES.md`

## Required reading order

1. `../context/README.md`
2. `../context/02_pranavesh/pranavesh-activity.md`
3. `../context/01_review_materials/reviewer-comments.md`
4. `../context/01_review_materials/IEEE_Access_33821_Reviewer_Dissection_Plan.txt` and its PDF when wording/layout matters
5. `../context/00_original_paper/` — exact pre-August paper snapshot and extracted text
6. `../context/02_pranavesh/` — PR #2/#4/#75/#77 patches and commit summaries
7. `../context/03_current_state/` — current dirty patch and revision artifacts
8. The clean `repo/` checkout, including `AGENTS.md`, current manuscript, code, tests, and committed experiment JSONs

Do not trust Claude's plan or repository prose automatically. Verify load-bearing claims against code, git history, tests, and committed result artifacts. Clearly label fact, inference, estimate, and unverified claim.

## Questions to answer

### A. What Pranavesh actually did

- Reconstruct the author-owned contribution in PRs #2, #4, #75, and #77.
- Distinguish authored code from merge-commit content and distinguish merged work from closed/unmerged work.
- For each contribution, say whether it remains in the current code/paper, was superseded, or is only historical.
- Inspect the actual diffs, not only PR titles or descriptions.

### B. Technical validation

- Review benchmark harnesses, pipeline changes, tests, config/entry points, and data assumptions for correctness and reproducibility.
- Run the strongest practical tests available in this environment. Record exact commands and real outputs. Do not claim full dataset/model validation if assets are absent.
- Check for stale paths, hidden machine-specific assumptions, nondeterminism, silent failures, metric mistakes, missing tests, and claims that exceed the evidence.
- Compare code claims to committed JSON artifacts and source. Pay special attention to micro-F1 vs macro-F1, sample counts, exact-match counts, and paper numbers.
- Review PR #77's LaTeX/TikZ layout changes and author/affiliation/funding edits as changes with scientific/submission consequences, not merely cosmetic edits. If no TeX compiler is available, record that blocker rather than inferring compilation success.

### C. Revision-plan closure

For all 12 reviewer comments (R1-1 through R1-6 and R2-1 through R2-6), classify the current state as satisfied, partial, or missing. Identify whether the current revision follows or deviates from Claude's plan, and whether the deviation is justified by evidence.

Explicitly check:

- title/abstract/conclusion scope: topological netlist vs component-value/OCR claims;
- VLM GT-box/oracle wording and detected-box evidence;
- the 31-image limitation, CIs, complexity/per-drafter evidence, and annotation-cost statement;
- crossover exposure and causal net-merge analysis;
- leave-one-module-out ablation vs strategy horse-race;
- one-scalar scale assumption and robustness evidence;
- unsupported Otsu and other numeric claims;
- author-only submission blockers and whether any author/affiliation/funding change needs confirmation.

## Notes format

Populate `notes/VALIDATION_NOTES.md` with:

1. A bottom-line verdict (safe to rely on / rely with caveats / do not rely without fixes).
2. A contribution-by-contribution table.
3. Findings ordered by severity, each with exact file/line, commit/PR, or artifact evidence.
4. The 12-comment coverage table.
5. Exact commands/checks run and outcomes.
6. A short, prioritized action list for Bosco. No speculative work items without an evidence-based trigger.

Do not edit production code. If a tiny scratch script is useful, place it under `notes/scratch/` and record it. Do not “fix” findings; this is an audit.
