# IEEE Access 33821 — Team Action Brief
## Independent validation (Astra, 2026-09-07) — what needs to be done

**Bottom line: NO-GO as-is, but fixable without new data.** The controlled results reproduce (join 0.890, VLM 0.923, synthetic 0.95 vs 0.36). What blocks resubmission is prose scope, contradictory claims, and package artifacts — not missing science.

Audit: detached `36b9a8e`. Full evidence in branch `validation/audit-20260907-astra` (`docs/research/experiments/validation-20260907-astra/`). No production code was changed by the audit.

## What Pranavesh did (verified)

- **PR #2 (merged):** experiment harness, portability paths, entry point, regression test. Real, retained infrastructure.
- **PR #4 (merged):** threshold/skeleton/Hough experiments, port gating, quality analysis, learned branch (in-sample, not held-out), MethodsX draft (now archived). Retained as experimental branches, not the production winner.
- **PR #75 (closed):** legacy-paper rewrite ("NetGuard"), generator tweaks. Not merged, not the live manuscript.
- **PR #77 (closed, integrated via #78):** TeX/TikZ layout, shortened abstract, author/funding edits ("Kumar", no-funding line, USC bio). Survives in ancestry — needs author confirmation, not just formatting sign-off.

August revision commits (`fe109ec`, `36b9a8e`) are Bosco-authored. Do not blame June PRs for August reviewer requests.

## Reviewer closeout — 12 comments

| Comment | Status | The one fix |
|---|---|---|
| R1-1 single corpus / N=31 | Partial | Soften "cross-drafter generalization" to descriptive within-corpus variation |
| R1-2 complex-device pins | **Gap** | Replace paragraph with capability table (evaluated vs generic-guess vs export); switches export as resistors today |
| R1-3 manual thresholds | Partial | Correct sign: fixed pixels 0.820 beats scale-relative 0.816 here; state bounded sensitivity, concede extremes untested |
| R1-4 no OCR / not simulatable | **Gap** | Scope sentence in abstract + intro + conclusion: topological recovery, illustrative SPICE export, values external |
| R1-5 small circuits | Partial | Add limit: counts (15 ≤5, 12 ≥10, max 14) do not prove dense-bus/multilayer coverage |
| R1-6 memristor cites | **Gap** | Add one polite decline paragraph in response; no citation needed |
| R2-1 stats / cost / roadmap | Partial | Add short roadmap paragraph (stratified expansion + timing logs as future); fix "same accuracy" language |
| R2-2 VLM oracle / cost claims | **Gap** | Rewrite as conditional GT-box evidence; drop 100–1000x and global-validity claims |
| R2-3 SPICE title | **Gap** | Retitle to Topological Netlists + running heads; rebuild PDF (committed PDF still says "simulation-ready") |
| R2-4 crossover merges | Partial | Report full tradeoff (C242: 27/4/0 → 19/0/8 on suppression); distinguish GT-box failure from detector-miss effect |
| R2-5 ablation | Partial | Fix caption: correct sign, base-only scope, occlusion never removed; fix clipped Table p.6 |
| R2-6 one scalar limit | Closed | None — keep disclosure, attach no new robustness claims |

Shared language fixes everywhere: nonsignificance is not equivalence; no global short-free guarantee; GT-box wire ceiling does not prove end-to-end dominance.

## Numbers to keep straight

- Join 0.890 (418/37/66) reproduced on all 31; perfect-wire 0.8898 — rounds same, not identical.
- 0.9755 = dedup 10°/18px config; mandated 12°/8px gives 0.9726. Label each table.
- Keep Otsu 0.789 (fresh rerun); do not substitute 0.828.
- VLM 0.923, 21/31 exact, 14/15 small — recomputed, CIs match.
- Reach sweep is macro 0.895–0.903 (not 0.898–0.903).
- Detected-box join 0.247 stays provisional; no detected-box VLM cell exists.

## Package checklist (all missing)

1. 12-row response (concern / response / action) — R1-6 decline included.
2. Highlighted PDF with every change marked.
3. Clean manuscript LaTeX + PDF, both layouts built, Table p.6 unclipped, C138 escaped, figures checked.
4. Author verification: byline order/spelling, affiliations, ORCIDs, bios, no-funding line, consent for any change.

## Next actions (in order)

1. Scope pass: title, abstract, intro, conclusion + device table (closes R1-4, R2-3, R1-2 prose).
2. VLM + stats pass: conditional comparison, roadmap paragraph, equivalence language removed (R2-2, R2-1).
3. Ablation/crossover/numbers pass: sign, range, tradeoff, config labels, Otsu kept (R1-3, R2-4, R2-5).
4. Response letter + R1-6 decline paragraph.
5. Author sign-off, then rebuild + visual check of both PDFs.

> After these prose/package corrections the revision is conditionally submittable. TeX compilation was unverified in the audit (no toolchain); acceptance cannot be guaranteed.
