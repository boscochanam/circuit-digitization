# Branch map — IEEE Access 33821 resubmission

> Work on `main`. Everything else is a frozen record.

| Branch / tag | Role | Who edits | Status |
|---|---|---|---|
| `main` | THE work line: full history + manuscript (`paper/ieee-paper/paper-access.tex`, `paper-build.tex`), code, review artifacts. Issues #82–88 track it. | Chris, Pranavesh, Bosco | Active |
| Tag `audit/evidence-20260908` | Evidence + plan snapshot (`IMPLEMENTATION_PLAN.md`, closeouts, team PDF, scratch JSONs, Phase-1/2 verification). Read-only record of why every number/decision holds. | Nobody (immutable) | Archived |
| Tags `v1.0.0` / `v1.0.1` | July public release (Zenodo DOIs, HF model card). | Nobody (immutable) | Archived |

Retired 2026-09-08: `revision/access-2026-33821`, `validation/audit-2026-33821`-style lines (merged or tagged; see git history). If you hold a local checkout of a deleted branch, switch to `main` — your work may need rebasing onto it.

Rules: keep `paper-access.tex` and `paper-build.tex` bodies in sync on every edit. Banned until Bosco signs off: author/funding/bio edits, email, submission.
