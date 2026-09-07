# IEEE Access 33821 — Team Action Brief

> **Bottom line: NO-GO as-is, fixable without new data.** Controlled results reproduce (join micro-F1 0.890 on 31 images, VLM 0.923, synthetic 0.95 vs 0.36). What blocks resubmission is prose scope, contradictory claims, and package artifacts. The implementation plan is written and the first fix has landed.

**Scope:** 7 Sept 2026. Covers the resubmission package only: manuscript, response letter, highlighted and clean PDFs, author verification. Full evidence in branch `validation/audit-20260907-astra`.

## Latest update

- **Implementation plan written** (`IMPLEMENTATION_PLAN.md` in the audit branch): D1–D4 verdicts, all 12 comments specified, package checklist, 7 OPEN items (all human-side). One planning run, ~20% of quota.
- **First fix applied and pushed** (merge branch, commit `823aef6`): method description now matches the OBB + nearest-pin implementation in both sources. Verified independently, `diff --check` clean.
- **Porting constraint found:** the two revision lines share no git history and patches don't transfer cleanly — T1 is hand porting of `paper-access.tex` plus 4 artifact files, never a merge.

## Work on hand (verified, ready to use)

- Controlled results: join 0.890 (418/37/66) on all 31, perfect-wire 0.8898, VLM 0.923 with CIs matching, synthetic L4 0.95 vs 0.36. Reproduced, not just reported.
- Retitle to Structural Circuit Netlists, fully implemented across title, heads, abstract, and conclusion.
- VLM recast as oracle diagnostic with provisional autonomous row (0.247) disclosed without CIs.
- Ablation and per-drafter tables with honest small-cell caveats.
- 12-point response draft with change index and an exact manuscript diff.
- Tau multipliers (0.62/0.30/0.20) and clamps confirmed in code; drafter counts and ablation numbers match committed JSONs.

## Decisions for the team (discuss first)

- **D1 — Porting strategy.** Proposal: hand-port the retitle, VLM recast, tables, and response draft onto the revision line, keeping the newer experiments and figures where they supersede.
- **D2 — Retitle lock.** Proposal: accept "Structural Circuit Netlists" (already implemented end-to-end).
- **D3 — Response starting point.** Proposal: use the existing 12-point draft as the base, converted into the IEEE template.
- **D4 — PDF ownership.** Proposal: one owner builds both layouts + highlighted copy and visually checks every page before anyone calls the package done.

## Reviewer closeout — status and the one fix per comment

| Comment | Status | The fix |
|---|---|---|
| R1-1 single corpus / N=31 | Partial | Descriptive within-corpus wording; no generalization claims |
| R1-2 complex-device pins | Gap | Capability table (evaluated vs generic-guess vs export) |
| R1-3 manual thresholds | Partial | Correct sign; concede extremes untested |
| R1-4 no OCR / not simulatable | Gap | Scope sentence in abstract + intro + conclusion |
| R1-5 small circuits | Partial | Dense-bus/multilayer limit sentence |
| R1-6 memristor cites | Gap | Polite decline paragraph in response |
| R2-1 stats / roadmap | Partial | Roadmap paragraph; fix "same accuracy" |
| R2-2 VLM oracle / cost | Gap | Conditional wording; drop cost multiples |
| R2-3 SPICE title | Gap | Retitle + running heads; rebuild PDF |
| R2-4 crossover merges | Partial | Full tradeoff; GT-box vs detector-miss wording |
| R2-5 ablation | Partial | Caption sign + scope; unclip Table p.6 |
| R2-6 one scalar limit | Closed | None — keep disclosure as-is |

Shared language fixes everywhere: nonsignificance is not equivalence; no global short-free guarantee; GT-box results do not prove end-to-end dominance.

## Task list (proposed owners — confirm together)

| # | Task | Proposed owner | Blocked by |
|---|---|---|---|
| T1 | Hand-port revision content onto the revision line; resolve conflicts keeping newer experiments | Bosco + Pranavesh | D1 |
| T2 | Lock retitle across title, heads, abstract, intro, conclusion | Bosco (decision) | D2 |
| T3 | Device capability table; fix switch-export wording | Assignee TBD | D1 |
| T4 | Response letter in IEEE template from existing draft, incl. R1-6 decline | Assignee TBD | D3 |
| T5 | VLM + stats prose pass (conditional wording, roadmap paragraph) | Assignee TBD | D1 |
| T6 | Numbers pass (ablation sign, reach label, config ledger, Otsu kept) | Assignee TBD | D1 |
| T7 | Rebuild both PDF layouts + highlighted copy; visual page check | Assignee TBD | D4, T1–T6 |
| T8 | Author verification: byline, affiliations, ORCIDs, bios, funding, consent | All | — |

## Numbers to keep straight

- Join 0.890 (418/37/66) reproduced on all 31; perfect-wire 0.8898 — rounds same, not identical.
- 0.9755 = dedup 10°/18px config; mandated 12°/8px gives 0.9726. Label each table.
- Keep Otsu 0.789 (fresh rerun); do not substitute 0.828.
- VLM 0.923, 21/31 exact, 14/15 small — recomputed, CIs match.
- Reach sweep is macro 0.895–0.903 (not 0.898–0.903). Detected-box join 0.247 stays provisional.

## Provenance (reference only — not the work plan)

Contributions arrived via PRs #2/#4 (merged harness and experiments), #75/#77 (closed drafts and layout), and the Sept 3 fork branch (retitle, recast, tables, response draft). Verification: audit branch `validation/audit-20260907-astra` (`VALIDATION_NOTES.md` findings F1–F16, `REVIEWER_CLOSEOUT.md`, `PHASE1_ASSESSMENT.md`, `IMPLEMENTATION_PLAN.md`, scratch reruns with pytest 495 passed). Merge branch holds the landed method fix. Decision letter Access-2026-33821 (13 Aug 2026).
