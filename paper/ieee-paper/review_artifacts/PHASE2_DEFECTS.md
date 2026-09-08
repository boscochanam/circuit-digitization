# Phase 2(d): grammar, mathematics and reference exception sweep

Anchors refer to current A/B at `02da5e6`; A/B = paper-access.tex/paper-build.tex. Read the scientific body, captions, tables, reference list, bios, live response and concept labels. This report distinguishes concrete source defects from editorial questions. No prose was rewritten. No manuscript build, bibliographic metadata lookup or PDF appearance judgment was performed.

## Concrete defects / inconsistencies

| ID | Anchor and exact evidence | Defect and disposition |
|---|---|---|
| G1 | A:480 / B:455, bio: “Engineering specializing from” | Dangling “specializing” lacks a specialization/complement. **HUMAN-ONLY:** author must approve intended wording/fact; never invent the specialization. |
| G2 | A:483 / B:458, bio: “She is life member” | Missing indefinite article. **HUMAN-ONLY:** protected bio edit requires authorization even though grammar is mechanical. |
| G3 | A:492–493 / B:467–468, bio: “..., Presently she is guiding 4 research scholar” | Mid-sentence capitalization and singular noun after 4. **HUMAN-ONLY:** approve grammar repair and verify the numerical career claim. |
| G4 | A:487 / B:462, bio: “research expertise is evident with her receiving many publications” | “Receiving publications” leaves the intended activity unclear. **HUMAN-ONLY:** clarify intended statement; no substitution of awards/authorship guessed. |
| M1 | A:205 / B:181: “mean F1 over error levels L1--L4”; A:215 / B:191 header L0/L1/L2/L3/L4; A:231 / B:207 caption “at each severity level” | Aggregation description contradicts per-level table/caption. **TEAM-DECISION:** describe averaging within each level, or explicitly distinguish any across-level chart statistic; retain stored scores. |
| M2 | A:108 / B:84: “caps per-pin degree”; A:149–151 / B:125–127 limits assignment rows/slots and then applies guards | Assignment capacity is not a cap on total final graph degree; base edges survive and a pin can participate in distinct assignment roles. **TEAM-DECISION:** narrow the shorthand to assignment capacities, or define/prove the stronger degree claim before retaining it. No proof or algorithm change supplied. |
| M3 | A:158 / B:134 completion caption “reconnects ... via min-cost $b$-matching”; `figures/completion_tikz.tex:33` “completion edge (min-cost b-matching)” | Caption/graphic shorthand fails to distinguish optimized assignment from the guarded, non-reassigned result. A:151/B:127 explicitly disclaims final optimality. **TEAM-DECISION:** qualify as assignment followed by guarded application, or explicitly scope “min-cost” to the pre-guard problem. |
| L1 | A:312 / B:288 `\includegraphics[width=0.82\textwidth]` inside unstarred `figure` | Single-column float is assigned a width greater than a column in the two-column templates. **TEAM-DECISION:** fit to column width or deliberately use a two-column float; accountable builder validates resulting pagination. Source geometry defect, not a measured rendered overflow here. |
| F1 | A:75 consumes `pipeline_overview.pdf`; native `pipeline_overview_tikz.tex:22` has corrected output label | Phase-1 extraction of consumed PDF still says SPICE Netlist / + simulation. **TEAM-DECISION:** builder regenerates the corrected concept PDF or harmonizes dependencies; then checks all three concept diagrams. Chart correction did not repair this graphic. |
| F2 | A:312/B:288 consumes `complexity_histogram.pdf`; caption A:313/B:289 defines electrical subset | Graphic says “SPICE-active components per image,” which differs from evaluated subset including ICs. **TEAM-DECISION:** correct presentation label from agreed population, preserve settled values; no new benchmark. |

The older red-team edge-3 formula, absent alpha and empty-solution objective defects are already repaired in the current methods (A:124–151/B:100–127). They are not reopened as current defects. The label `sec:vlm_connectivity` sits within Related Work (A:105/B:81); it resolves to that section, not a separately numbered subsection. This is a valid section reference, with potential navigational specificity to review, not an unresolved reference.

## Reference-format gaps (facts not externally revalidated)

| ID | Anchor / key | Visible omission or inconsistency; next action |
|---|---|---|
| R1 | A:440 / B:416, `kulkarni2025enhancing` | Proceedings citation ends with workshop/year, without page range, article locator, DOI or URL. **TEAM-DECISION:** complete from the authoritative publication record or document unavailable locator; do not invent metadata. |
| R2 | A:447 / B:423, `netlistify2025` | Proceedings/year only, likewise no pages/article locator/DOI/URL. Same completion requirement as R1. |
| R3 | A:428 / B:404, `instanceseg2023` | DOI is present, but proceedings page range is absent. **TEAM-DECISION:** complete the locator or approve DOI-only format under the chosen reference convention. |
| R4 | A:423,425 versus A:427,430 / corresponding B:399,401 versus B:403,406 | DOI presentation alternates “[Online]. Available: https://doi.org/...” and “doi: ...”. Observable style inconsistency; **TEAM-DECISION:** choose the template's consistent convention. Neither form is declared factually wrong here. |
| R5 | A:432,448 / B:408,424, `jocher2023yolo`, `circuitnet` | Mutable GitHub references have no cited release/commit or access date. **TEAM-DECISION:** choose an archival/versioned reference or add a genuinely verified access date when checked. No date/version is invented. |

These are source completeness/consistency findings, not claims that a particular DOI, author list, year, title or page number is wrong. Bibliographic-fact verification remains technical work against primary records; final reference-format approval belongs to the named editor/author. R1-6's two suggested references were intentionally declined in the response and are not missing citation-key defects.

## Editorial questions, not automatic fixes

- A:97/B:73 “as prior systems do” generalizes prior-system representation without a bounded set at that clause; the repeated “representation ... that is what makes ...” is also cumbersome. **TEAM-DECISION:** narrow to cited implementations or retain with specific support; do not silently rewrite the contribution claim.
- A:379/B:355 uses `$\pm$0.03--0.05` as shorthand for bootstrap interval widths. The recorded intervals need not be symmetric. **TEAM-DECISION:** show actual endpoints or label the range as approximate widths; do not infer symmetric confidence bounds.
- A:354/B:330 displays 12% for the dual-R-loop simulation rate. Its stored 12.5% rounds to 12% with ties-to-even in the phase-1 ledger. **TEAM-DECISION:** retain a documented rounding rule or show one decimal consistently; do not call 12% a failed recomputation.
- Histogram extracted title “e 31-image...” may indicate clipping; extraction alone cannot establish visual clipping. **HUMAN-ONLY:** final page/figure appearance judgment after the builder's mechanical checks.

## Mechanical source checks

`phase2_evidence/source_checks.json`: both sources have 19 unique labels, zero unresolved refs/cites, 26 bibliography items, zero uncited entries and first-citation order matching bibliography order. Environment nesting matches; dollar-delimiter counts are even. These are source checks, not a TeX compile or proof of correct mathematical typesetting. PASS for resolution/order; rendered math/reference/page approval remains unverified.

Inventory completion: PASS. Grammar/math/reference readiness: FAIL/unverified pending the specifically identified dispositions. No author-field or substantive wording change was made in this item.
