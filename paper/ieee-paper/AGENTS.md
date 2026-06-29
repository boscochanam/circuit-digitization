# IEEE Paper — Agent Instructions

> Synced 2026-06-29 to the current paper. This file had drifted (old
> "Degree-Budget Topology Join" title, Mimo VLM, 0.94/0.36 numbers, 134-image
> join claim). The authoritative numbers live in
> `docs/research/experiments/SUMMARY.md` and
> `docs/research/ieee-access-session-handoff.md`; this is a quick orientation.

## Live sources (keep the two in sync)

- **`paper-access.tex`** — IEEE Access submission source (`\documentclass{ieeeaccess}`).
- **`paper-build.tex`** — IEEEtran, for local `pdflatex` builds. Same body as
  `paper-access.tex`; only the preamble/front-matter differs. **Any body edit
  must be applied to BOTH.**
- `paper.tex` — superseded single-file draft (old framing/title). Not built; kept
  only as history. Do not edit; prefer archiving it.

## IEEE Access template kit (2026-05-13)

Runtime files are in **`ieeeaccess/`** (`ieeeaccess.cls`, bundled `IEEEtran.cls`,
fonts, `bullet.png`, etc.). Official sample front matter is
`ieeeaccess/access-sample.tex` (do not submit; reference only).

Local compile from this directory:

```bash
latexmk -pdf paper-access.tex
```

(`latexmkrc` prepends `./ieeeaccess//` to `TEXINPUTS` and `TEXFONTMAPS`.)

## TODO — align `paper-access.tex` with the official template

**Structural alignment is done** (2026-06-29): front-matter order, `\titlepgskip`,
`\headeretal`, `keywords` env, `bm` preamble match `ieeeaccess/access-sample.tex`.
Compile with `latexmk -pdf paper-access.tex` and eyeball page 1.

**Still author-owed before submission** (no new prose needed from agents unless asked):

1. ORCIDs on author line (`\orcidlink{...}` per author).
2. Finalize `IEEEbiographynophoto` text for Bosco Chanam and Chris Dcosta (Pranav's is drafted).
3. Real `\history` and `\doi` when IEEE assigns them.
4. Optional: `\IEEEmembership{...}` if any author is an IEEE member.

## Title

From Hand-Drawn Schematics to SPICE Netlists: A Deterministic Pipeline with
Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark

**Authors:** Bosco Chanam, Chris Dcosta, Pranavesh Talupuri (USC)

## Framing

A complete **deterministic pipeline** (occlusion-first wire extractor → endpoint
representation → endpoint-graph join → degree-budget completion) **plus the first
human-verified net-level connectivity benchmark** for hand-drawn circuits. The
*join* is the primary contribution and the **primary metric is component-pair
micro-F1** (macro reported alongside). The VLM comparison is a reference point,
not the story.

## Section structure

1. Introduction — problem, threefold challenge, VLM-as-alternative (tested in §V), contributions
2. Related Work — digitization/netlist extraction; datasets/benchmarks; VLMs/LLMs; wire detection & graph connectivity
3. Method — pipeline overview (6 stages); endpoint-graph join (**5 edge types**); degree-budget completion (min-cost b-matching)
4. Synthetic Evaluation Framework — 15 authored circuits; 5 error categories × 4 severity levels; metrics
5. Results — wire detection; synthetic join leaderboard; **real-image net-level eval (N=31)**; per-circuit; **VLM experiment**
6. Discussion / Limitations / Conclusion

Endpoint-graph **edge types**: (1) wire body, (2) endpoint–endpoint, (3)
endpoint–pin (component-first, directional), (4) endpoint–wire-body (T-junction),
(5) pin–wire-body (rail-tap). Implemented in `wire_detection/core/join_graph.py`.

## Key numbers (re-verified 2026-06-28; sources in `docs/research/experiments/`)

- **Wire detection F1 = 0.976** (134 CGHD-1152 images; Sauvola + 16px anchor).
- **Real net-level GT: N=31 human-verified** (`ground_truth/real_nets_verified.json`).
  Join micro-F1 (detected wires, GT component boxes):
  - **scale_completion (default) = 0.890** (P 0.919, R 0.864, macro 0.901)
  - degree_budget 0.829 · graph_scale 0.816 · graph_rescue 0.787 · radius/production 0.667
  - classical baselines: Hough+proximity 0.805 · connected-components 0.624
  - **perfect wires = 0.890** (micro unchanged → detection is not the bottleneck)
- **Synthetic L4 leaderboard:** scale_completion 0.95 ≥ degree_budget 0.94 ≥
  graph_rescue 0.90 ≥ graph_scale 0.85; radius union-find 0.36.
- **VLM (Claude Opus 4.8)** on the same 31: micro-F1 **0.923** (P 0.97, R 0.88,
  macro 0.949), exact on 21/31. Paired **VLM − ours = +0.033, 95% CI
  [−0.009, +0.078]** → statistically indistinguishable; but ~10^5 tokens/image,
  free-form, non-simulatable. Treated as an upper reference, not a module to ship.
- **Component detection:** 88.5% mAP@0.5 (16 classes; crossover recall 70.7%).

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
- Pipeline examples (Fig 2): `figures/pipeline_examples/{C37-D2-P4,C111-D1-P1}-jpg.png` (F1=1.0 on both).

## Component detection model

- `models/component_detection/yolo26m_obb_16class_aug.pt`
- HuggingFace: <https://huggingface.co/boscochanam/circuit-component-detector>

## Still author-owed (before submission)

Template alignment (see **TODO** above), ORCIDs, author biographies, funding line,
and publication dates.
