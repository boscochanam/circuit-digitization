# IEEE Access 33821 — Team Action Brief

> **Bottom line: NO-GO as-is, fixable without new data.** The controlled results reproduce (join micro-F1 0.890 on 31 images, VLM 0.923, synthetic 0.95 vs 0.36). What blocks resubmission is prose scope, contradictory claims, and package artifacts — not missing science.

**Scope:** Independent Astra audit of Pranavesh's work + 12-comment reviewer closeout, 7 Sept 2026. Audit base: detached commit `36b9a8e`. Full evidence in branch `validation/audit-20260907-astra`. No production code was changed by the audit.

## What Pranavesh did (verified)

- **PR #2 (merged):** experiment harness, portability paths, entry point, regression test. Real, retained infrastructure.
- **PR #4 (merged):** threshold/skeleton/Hough experiments, port gating, quality analysis, learned branch (in-sample, not held-out), MethodsX draft (now archived). Retained as experimental branches, not the production winner.
- **PR #75 (closed):** legacy-paper rewrite ("NetGuard"), generator tweaks. Not merged, not the live manuscript.
- **PR #77 (closed, integrated via #78):** TeX/TikZ layout, shortened abstract, author/funding edits. Survives in ancestry — needs author confirmation.

August revision commits (`fe109ec`, `36b9a8e`) are Bosco-authored.

## Reviewer closeout — status and the one fix per comment

| Comment | Status | The one fix |
|---|---|---|
| R1-1 single corpus / N=31 | Partial | Soften "cross-drafter generalization" to descriptive within-corpus variation |
| R1-2 complex-device pins | Gap | Capability table (evaluated vs generic-guess vs export); switches export as resistors today |
| R1-3 manual thresholds | Partial | Correct sign: fixed pixels 0.820 beats scale-relative 0.816 here; concede extremes untested |
| R1-4 no OCR / not simulatable | Gap | Scope sentence in abstract + intro + conclusion: topological recovery, illustrative export |
| R1-5 small circuits | Partial | Add limit: counts (15 ≤5, 12 ≥10, max 14) do not prove dense-bus/multilayer coverage |
| R1-6 memristor cites | Gap | One polite decline paragraph in response; no citation needed |
| R2-1 stats / cost / roadmap | Partial | Roadmap paragraph (stratified expansion + timing logs as future); fix "same accuracy" |
| R2-2 VLM oracle / cost claims | Gap | Conditional GT-box wording; drop 100–1000x and global-validity claims |
| R2-3 SPICE title | Gap | Retitle to Topological Netlists + running heads; rebuild PDF |
| R2-4 crossover merges | Partial | Full tradeoff (C242: 27/4/0 → 19/0/8 on suppression); GT-box vs detector-miss effects |
| R2-5 ablation | Partial | Fix caption sign + base-only scope; fix clipped Table p.6 |
| R2-6 one scalar limit | Closed | None — keep disclosure, attach no new robustness claims |

Shared language fixes everywhere: nonsignificance is not equivalence; no global short-free guarantee; GT-box wire ceiling does not prove end-to-end dominance.

## Numbers to keep straight

- Join 0.890 (418/37/66) reproduced on all 31; perfect-wire 0.8898 — rounds same, not identical.
- 0.9755 = dedup 10°/18px config; mandated 12°/8px gives 0.9726. Label each table.
- Keep Otsu 0.789 (fresh rerun); do not substitute 0.828.
- VLM 0.923, 21/31 exact, 14/15 small — recomputed, CIs match.
- Reach sweep is macro 0.895–0.903 (not 0.898–0.903); detected-box join 0.247 stays provisional.

## Package checklist (all missing at audit time)

1. 12-row response (concern / response / action) — R1-6 decline included.
2. Highlighted PDF with every change marked.
3. Clean manuscript LaTeX + PDF, both layouts built, Table p.6 unclipped, C138 escaped, figures checked.
4. Author verification: byline order/spelling, affiliations, ORCIDs, bios, no-funding line, consent for any change.

## Next actions (in order)

1. **Scope pass:** title, abstract, intro, conclusion + device table (closes R1-4, R2-3, R1-2 prose).
2. **VLM + stats pass:** conditional comparison, roadmap paragraph, equivalence language removed (R2-2, R2-1).
3. **Ablation/crossover/numbers pass:** sign, range, tradeoff, config labels, Otsu kept (R1-3, R2-4, R2-5).
4. **Response letter** + R1-6 decline paragraph.
5. **Author sign-off, then rebuild + visual check** of both PDFs.

> After these prose/package corrections the revision is conditionally submittable. TeX compilation was unverified in the audit (no toolchain); acceptance cannot be guaranteed.

## Finding index — where to look in the full notes

High severity: F1 global structural guarantee false · F2 scope/bottleneck exceeds experiment · F3 stale PDF vs source vs package · F4 ablation sign reversed · F5 wire-config identity (0.9755 vs 0.9726) · F6 entry points bypass model-source switch · F7 detected-box evidence provisional. Medium: F8 crossover causality without safe fix · F9 empty-data eval reports F1 1.0 · F10 learned branch in-sample · F11 ablation gaps · F12 equivalence/cost unproven · F13 drafter/device precision · F14 stale algorithm prose · F15 byline/funding unverified. Lower: F16 machine-specific paths and figure issues.

## Sources

Full evidence in branch `validation/audit-20260907-astra`: `VALIDATION_NOTES.md` (F1–F16), `REVIEWER_CLOSEOUT.md`, `PHASE1_ASSESSMENT.md`, scratch reruns (pytest 495 passed, join/synthetic/wire/CI JSONs). Audit base `36b9a8e`; decision letter Access-2026-33821 (13 Aug 2026).
