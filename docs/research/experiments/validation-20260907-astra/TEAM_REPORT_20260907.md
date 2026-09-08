# IEEE Access 33821 — Team Action Brief

> **Bottom line: manuscript prose is substantially executed and verified; the package is not yet built.** Controlled results reproduce (join micro-F1 0.890 on 31 images, VLM 0.923, synthetic 0.95 vs 0.36). Retitle applied, overclaims removed, method prose made code-faithful, response scaffolding written. What remains: fork hand-port (T1), template conversion (T4), PDF builds + visual check (T7), author verification (T8).

**Scope:** 8 Sept 2026. Covers the resubmission package only: manuscript, response letter, highlighted and clean PDFs, author verification. Full evidence in branch `validation/audit-20260907-astra`; work line is `revision/access-2026-33821-merge-20260907` (pushed, clean).

## Latest update

- **Execution run landed** (merge line, 8 commits through `cefe77b`, all independently verified): structural-netlist retitle in both sources *including* running heads; banned-claim sweep (zero residue, pipeline-diagram node corrected); B:100/B:124 rewritten from code (fixed alpha 0.35, fallback condition, mandatory assignment); crossover/ablation qualifications; response scaffolding with change index. A/B body edits byte-identical outside template headers.
- **Plan amended after adversarial review** (audit branch): D3 flipped to MODIFY (regenerate responses from the evidence ledger, don't just fix device passages); numeric provenance OPENs closed with file paths and SHA256s; freeze dependencies made explicit.
- **D2 LOCKED:** "Structural Circuit Netlists" is in the manuscript.
- **Porting constraint stands:** the two revision lines share no git history — T1 is hand porting, never a merge.

## Work on hand (verified, ready to use)

- Controlled results: join 0.890 (418/37/66) on all 31, perfect-wire 0.88983 (420/40/64), VLM 0.923 with CIs matching, synthetic L4 0.95 vs 0.36. Reproduced, not just reported.
- Retitle applied end-to-end (title, heads, abstract, conclusion, diagram node).
- VLM recast as oracle diagnostic with provisional autonomous row (0.247) disclosed without CIs.
- Ablation and per-drafter tables with honest small-cell caveats; numeric provenance closed (SHAs on record).
- Response scaffolding (concern/response/action) with change index; R1-6 decline drafted.
- Tau multipliers (0.62/0.30/0.20) and clamps confirmed in code; drafter counts and ablation numbers match committed JSONs.

## Decisions (D2 locked; D1, D3, D4 need a nod)

- **D1 — Porting strategy.** Hand-port the fork's retitle, VLM recast, tables, and response draft onto the merge line, keeping the newer experiments and figures where they supersede. (T1, Pranavesh.)
- **D2 — Retitle lock. LOCKED.** "Structural Circuit Netlists" — already in both sources.
- **D3 — Response starting point. Revised:** use the fork draft's *organization only*; regenerate every factual sentence against the final manuscript and evidence ledger. (T4, Pranavesh.)
- **D4 — PDF ownership.** One builder, explicit order: clean IEEEtran, then clean Access, then highlighted copy; author facts before source freeze; final consent on the frozen package. (T7, Chris.)

## Reviewer closeout — status and the one fix per comment

| Comment | Status | The fix |
|---|---|---|
| R1-1 single corpus / N=31 | Partial | Descriptive within-corpus wording; no generalization claims |
| R1-2 complex-device pins | Gap | Capability table (evaluated vs generic-guess vs export) |
| R1-3 manual thresholds | In manuscript | Alpha fixed at 0.35 with condition; extremes conceded untested |
| R1-4 no OCR / not simulatable | In manuscript | Scope sentences + retitle + diagram node |
| R1-5 small circuits | Partial | Dense-bus/multilayer limit sentence |
| R1-6 memristor cites | Drafted | Polite decline paragraph in response scaffolding |
| R2-1 stats / roadmap | Partial | Roadmap paragraph; fix "same accuracy" |
| R2-2 VLM oracle / cost | In manuscript | Conditional wording; cost multiples dropped |
| R2-3 SPICE title | Done | Retitle + running heads; PDF rebuild pending (T7) |
| R2-4 crossover merges | Partial by design | Join tradeoff supplied; detector-miss effect honestly unmeasured |
| R2-5 ablation | Partial | Genuine table; no causal over-inference |
| R2-6 one scalar limit | Closed | None — keep disclosure as-is |

Shared language now enforced: nonsignificance is not equivalence; no global short-free guarantee; component-pair F1 does not certify pin topology; GT-box results do not prove end-to-end dominance.

## Task list (owners assigned — verify, don't rewrite)

| # | Task | Owner | State |
|---|---|---|---|
| T1 | Hand-port fork content onto the merge line; newer experiments win | Pranavesh (#81) | Not started |
| T2 | Retitle application | Astra (done), Bosco locked | Done |
| T3 | Device capability table; fix switch-export wording | Chris (#83) | Not started |
| T4 | Response letter in IEEE template from scaffolding | Pranavesh (#84) | Scaffolding done; conversion open |
| T5 | VLM + stats prose pass | Chris (#85, joint with T6) | Drafted by Astra; needs owner read-through |
| T6 | Numbers pass + claim sweep + method fidelity | Chris (#85) | Drafted by Astra; needs owner read-through |
| T7 | Rebuild both PDF layouts + highlighted copy; visual page check | Chris (#86) | Blocked until T1 lands |
| T8 | Author verification: byline, affiliations, ORCIDs, bios, funding, consent | All (#87) | Open; placeholders at A:35–36 inventoried |

Bosco: D1/D3/D4 nod + verification review + portal submit (#88).

## Numbers to keep straight

- Join 0.890 (418/37/66) reproduced on all 31; perfect-wire 0.88983 (420/40/64) — rounds same, not identical.
- 0.9755 = dedup 10°/18px config; mandated 12°/8px gives 0.9726. Label each table.
- Keep Otsu 0.789 (fresh rerun); do not substitute 0.828.
- VLM 0.923, 21/31 exact, 14/15 small — recomputed, CIs match.
- Reach sweep is macro 0.895–0.903 (not 0.898–0.903). Detected-box join 0.247 stays provisional.
- Provenance SHAs for the three JSONs are recorded in the amended plan — cite them, don't re-derive them.

## Provenance (reference only — not the work plan)

Fork branch (Sept 3: retitle, recast, tables, response draft) hand-ports onto the merge line. Verification: audit branch `validation/audit-20260907-astra` (`VALIDATION_NOTES.md` F1–F16, `REVIEWER_CLOSEOUT.md`, `IMPLEMENTATION_PLAN.md` amended, `PLAN_REDTEAM.md`, scratch JSONs with pytest 495 passed). Merge line holds the executed prose. Decision letter Access-2026-33821 (13 Aug 2026).
