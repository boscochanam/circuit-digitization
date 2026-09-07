# IEEE Paper — Agent Instructions

> Revision state, Sept 2026. Supersedes the 2026-06-29 orientation below in every
> place they conflict. Numbers still trace to `docs/research/experiments/`
> (`SUMMARY.md`, `ieee-access-session-handoff.md`); prose framing follows the
> resubmission — scope discipline, no overclaims.

## Active work (do this first)

- **Work line:** `revision/access-2026-33821-merge-20260907` — all T1–T8 edits land here.
- **Plan (read before touching the manuscript):** `IMPLEMENTATION_PLAN.md` on branch
  `validation/audit-2026-09-07-astra` (D1–D4 verdicts, per-comment specs, OPEN items).
  Team brief: `TEAM_REPORT_20260907.pdf` (same branch).
- **Fork source:** `tkprnv/review/ieee-access-revision-2026-09` (`10c1b92`) holds the
  retitle, VLM recast, ablation + per-drafter tables, and response draft.
  **Critical:** the fork shares no git history with this line — hand-port prose and
  artifacts file by file. Never merge or rebase across; the fork patch does not apply cleanly.
- **Issues #81–88** track T1–T8 + closeout. Close an issue only when its acceptance check passes.
- **Banned until human sign-off:** author names/affiliations/funding/bios edits, pushes to
  any branch but the merge line, email, PDF judgments beyond mechanical checks.

## Live sources (keep the two in sync)

- **`paper-access.tex`** — IEEE Access template (Overleaf). Submission source.
- **`paper-build.tex`** — IEEEtran, for local `pdflatex` builds. Same body as
  `paper-access.tex`; only the preamble/front-matter differs. **Any body edit
  must be applied to BOTH.**
- `paper.tex` — superseded single-file draft (old framing/title). Not built; kept
  only as history. Do not edit; prefer archiving it.

## Title

**PENDING D2.** Proposal (implemented in the fork, recommended): "From Hand-Drawn
Schematics to **Structural Circuit Netlists** …". Do NOT ship "SPICE netlists" /
"simulation-ready" product claims under either title — the pipeline reads no
component values. Retitle lock is Bosco's decision; apply mechanically once locked (T2).

**Authors (matches committed manuscript; changes need written consent of all):**
Bosco Chanam, Chris Dcosta, Pranavesh Kumar Talupuri, Shwetambari A. Chiwhane,
Ashay Kumar Singh, Arghadeep Das.

## Framing (resubmission discipline — violations fail the one-shot review)

- Structural component-pair connectivity on one hand-drawn corpus (CGHD-1152, N=31
  human-verified). Micro-F1 primary, macro alongside.
- The VLM run is an **oracle-component-box diagnostic**, not an end-to-end comparison.
  Never write "fair," "statistically indistinguishable" as equivalence, cost multiples
  (100–1000x), or geometric-superiority claims.
- A CI that includes zero establishes **nonsignificance, not equivalence**.
- No global short-free / structurally-valid-by-construction guarantees.
- GT-box wire results do not transfer to autonomous end-to-end claims (provisional
  detected-box join micro-F1 0.247, no CIs).

## Key numbers (values verified; interpretations per resubmission)

- **Wire detection F1 = 0.976** (134 CGHD-1152 images; see ledger: 0.9755 = dedup
  10°/18px config, 12°/8px gives 0.9726 — label each table; Otsu stays 0.789).
- **Real net-level GT: N=31 human-verified** (`ground_truth/real_nets_verified.json`).
  Join micro-F1 (detected wires, GT component boxes):
  - **scale_completion (default) = 0.890** (P 0.919, R 0.864, macro 0.901)
  - degree_budget 0.829 · graph_scale 0.816 · graph_rescue 0.787 · radius/production 0.667
  - classical baselines: Hough+proximity 0.805 · connected-components 0.624
  - **perfect wires = 0.8898** (rounds to 0.890; conditional on annotated boxes —
    NOT proof about the autonomous bottleneck).
- **Synthetic L4 leaderboard:** scale_completion 0.95 ≥ degree_budget 0.94 ≥
  graph_rescue 0.90 ≥ graph_scale 0.85; radius union-find 0.36.
- **VLM (Claude Opus 4.8)** on the same 31: micro-F1 **0.923** (P 0.97, R 0.88,
  macro 0.949), exact on 21/31. Paired diff +0.033, 95% CI [−0.009, +0.078].
- **Component detection:** 88.5% mAP@0.5 (16 classes; crossover recall 70.7%).
- **Reach sweep is macro** 0.895–0.903 (not 0.898–0.903).

## Default join strategy

`DEFAULT_STRATEGY = "scale_completion"` (`wire_detection/core/join_strategies.py`):
high-precision scale-relative endpoint-graph base (no end-extension / dead-end
rescue) + degree-budget floating-pin completion at reach 4×scale. `degree_budget`
and `graph_rescue` remain registered as fallbacks/ablations.

**Strategy names are descriptive in the paper** (code keeps the identifiers):
`scale_completion` → "scale-relative graph + completion"; `degree_budget` →
"rescue graph + completion"; `graph_scale`/`graph_rescue` → "...graph (base)";
`production` → "radius union-find (legacy)".

## Figures

- Concept diagrams are **native TikZ**: `figures/{pipeline_overview,endpoint_graph,completion}_tikz.tex` (`\input` from both `.tex`).
- Data bar charts (matplotlib): `figures/{wire_benchmark,join_comparison,real_join_comparison}.pdf`.
- Pipeline examples (Fig 2): C37 + C111 panels — counts must be tied to the generator's
  exact image/config, never copied from the benchmark.
- Ablation table: fixed-pixel base 0.820 beats scale-relative 0.816 here; full-pipeline
  ties at 0.890 are a negative result, not proof mechanisms are dispensable.

## Component detection model

- `models/component_detection/yolo26m_obb_16class_aug.pt`
- HuggingFace: <https://huggingface.co/boscochanam/circuit-component-detector>

## Still author-owed (before submission — humans only, T8)

ORCIDs, author biographies, funding/acknowledgment line, publication dates, byline
consent, and the exact `ieeeaccess.cls` render on Overleaf (local cls incompatible
with TeX Live 2023).
