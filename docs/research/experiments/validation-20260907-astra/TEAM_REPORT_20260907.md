# IEEE Access 33821 — Team Action Brief

> **Bottom line: NO-GO as-is, fixable without new data.** Controlled results reproduce (join micro-F1 0.890 on 31 images, VLM 0.923, synthetic 0.95 vs 0.36). What blocks resubmission is prose scope, contradictory claims, and package artifacts. Two revision lines now exist — the first decision is how to merge them.

**Scope:** Independent audit (Astra, 7 Sept 2026) of the revision work + 12-comment reviewer closeout. Audit base: detached commit `36b9a8e`. Full evidence in branch `validation/audit-20260907-astra`. No production code was changed by the audit.

## Latest update — plan complete, first fix landed

- **Implementation plan written** (`IMPLEMENTATION_PLAN.md` in the audit branch): D1–D4 verdicts, all 12 comments specified, package checklist, 7 OPEN items (all human-side). One Astra planning run, ~20% of quota.
- **First fix applied and pushed** (merge branch `revision/access-2026-33821-merge-20260907`, commit `823aef6`): method description now matches the OBB + nearest-pin implementation in both sources. Verified independently, `diff --check` clean.
- **Key finding for T1:** the fork line and the revision line share no git history (duplicated commits split the ancestry), and the fork's patch does not apply cleanly. T1 is hand surgery on `paper-access.tex` plus the 4 artifact files — never a merge or rebase.
- **Pushback resolved:** crossover rerun withdrawn (artifact was present); method fix applied (above); human PDF review stays T7's job.

## Where things stand — two revision lines

| Line | Base | Contains | Still missing |
|---|---|---|---|
| Bosco branch (`revision/access-2026-33821` @ `36b9a8e` + working tree) | Aug revision | Newer experiments: complexity histogram, C242 causal detail, full CI treatment, rebuilt figures, C138 escape, detected-box row | Retitle not locked; no response letter; no highlighted/clean PDFs |
| Pranavesh fork (`review/ieee-access-revision-2026-09` @ `10c1b92`, Sept 3) | July `main` | Structural retitle, VLM recast, ablation + per-drafter tables, 12-point response draft with change index | Stale base; no compiled PDFs; no template conversion; no device table |

Fork facts verified deterministically: change diff is byte-exact, tau multipliers (0.62/0.30/0.20) and pixel clamps match code, drafter cell counts and ablation numbers match committed JSONs. Earlier contributions (PR #2 harness, PR #4 experiments, PR #75 closed draft, PR #77 layout integrated via #78) are retained infrastructure, not the live revision question.

## Decisions for the team (discuss first)

- **D1 — Merge direction.** Proposal: rebase the fork onto the revision branch, keeping the newer experiments and figures where they supersede carried-forward values.
- **D2 — Retitle lock.** Proposal: accept "Structural Circuit Netlists" (the fork implements it; the plan recommended it).
- **D3 — Response starting point.** Proposal: fork draft as the base, converted into the IEEE template, plus the missing author-verification rows.
- **D4 — PDF ownership.** Proposal: one owner builds both layouts + highlighted copy and visually checks every page before anyone calls the package done.

## Reviewer closeout — status, fix, and who already has it

Status describes the Bosco branch. "Fork" = whether Pranavesh's branch already contains the fix.

| Comment | Status | The fix | Fork |
|---|---|---|---|
| R1-1 single corpus / N=31 | Partial | Descriptive within-corpus wording; no generalization claims | Partial |
| R1-2 complex-device pins | Gap | Capability table (evaluated vs generic-guess vs export) | Partial |
| R1-3 manual thresholds | Partial | Correct sign; concede extremes untested | Partial |
| R1-4 no OCR / not simulatable | Gap | Scope sentence in abstract + intro + conclusion | Yes |
| R1-5 small circuits | Partial | Dense-bus/multilayer limit sentence | Partial |
| R1-6 memristor cites | Gap | Polite decline paragraph in response | Yes |
| R2-1 stats / roadmap | Partial | Roadmap paragraph; fix "same accuracy" | Partial |
| R2-2 VLM oracle / cost | Gap | Conditional wording; drop cost multiples | Yes |
| R2-3 SPICE title | Gap | Retitle + running heads; rebuild PDF | Yes |
| R2-4 crossover merges | Partial | Full tradeoff; GT-box vs detector-miss wording | Partial |
| R2-5 ablation | Partial | Caption sign + scope; unclip Table p.6 | Yes |
| R2-6 one scalar limit | Closed | None — keep disclosure as-is | Yes |

Shared language fixes everywhere: nonsignificance is not equivalence; no global short-free guarantee; GT-box results do not prove end-to-end dominance.

## Task list (proposed owners — confirm together)

| # | Task | Proposed owner | Blocked by |
|---|---|---|---|
| T1 | Rebase fork onto revision branch; resolve conflicts keeping newer experiments | Bosco + Pranavesh | D1 |
| T2 | Lock retitle across title, heads, abstract, intro, conclusion | Bosco (decision) | D2 |
| T3 | Device capability table; fix switch-export wording | Assignee TBD | D1 |
| T4 | Response letter in IEEE template from fork draft, incl. R1-6 decline | Assignee TBD | D3 |
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

## Sources

Full evidence in branch `validation/audit-20260907-astra`: `VALIDATION_NOTES.md` (findings F1–F16), `REVIEWER_CLOSEOUT.md`, `PHASE1_ASSESSMENT.md`, scratch reruns (pytest 495 passed, join/synthetic/wire/CI JSONs). Audit base `36b9a8e`; decision letter Access-2026-33821 (13 Aug 2026).
