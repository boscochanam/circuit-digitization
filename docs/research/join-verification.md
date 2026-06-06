# Node-Joining: Verification, Findings & Tooling

Living doc for understanding, verifying, and improving the **node-joining**
(netlist construction) stage — separate from wire *detection*. Added while
investigating a report that "joining isn't great" despite the high detection F1.

## TL;DR

- **Detection F1 (0.83) ≠ join quality.** They measure different things; there is
  **no end-to-end netlist-correctness metric**. The high badge does not mean the
  joins are right.
- The production join (`core/netlist.py::build_netlist`) **over-merges**: on a
  94-image batch, ~58 components/image collapse into **~3.5 nets** (a healthy
  schematic has dozens), with **6.7% of components shorted by self-loops** and
  **80% "connected" only because a few giant nets swallow everything**.
- Root cause is the **join mechanism**, not the concept: it ties a wire-end to
  **every pin within 30px** (not the nearest), plus transitive union-find — so
  dense areas / junctions / mislocated pins cause runaway merges.

> **⏭ SUPERSEDED — the current best join is the endpoint-graph `graph_rescue`**
> (the new default). It beats every attach-rule strategy below on the robust
> `join_quality` metric (53/58 images vs production). See the
> **Endpoint-graph join** section further down. The ranking below is the earlier
> attach-rule-only study (kept for history); among *those*, `nearest2_30` was best.

## RECOMMENDED STRATEGY RANKING (1,648-image eval, by `balanced` score) — historical

Ranked by the eye-matching **`balanced`** metric (over-merge + under-connection).
Production is only 4th. The new methods take the top 3.

| # | strategy | balanced | wires used | why |
|---|---|---:|---:|---|
| 🥇 1 | **`nearest2_30`** | **0.186** | **86%** | Best overall: each wire-end ties its 2 nearest pins → connects the most wire while limiting over-grab. Simplest winner. |
| 🥈 2 | **`junction_extend_n1`** | 0.188 | 85% | Best "engineered" stack: junction-aware pins + extend ends + nearest. **Lowest dangling**, few shorts — best starting point for **manual annotation** (fewest hard-to-fix over-merges). |
| 🥉 3 | **`extend12_n1_30`** | 0.192 | 83% | Nearest + 12px end-extension. **Fewest false shorts (364)** of the well-connected strategies. |
| 4 | `production` (current default) | 0.236 | 76% | Over-merges (5821 shorts, 2197 giant nets) and still only uses 76% of wires. Mid-pack. |
| … | (anchored / density / nearest1 / mutual) | 0.25–0.35 | 57–75% | Either over-conservative (under-connect) or radius-only tweaks. `mutual_30` has the *best composite* but is **2nd-worst balanced** — it under-connects (57% wires). |

**Picks:**
- **Default / general best → `nearest2_30`.**
- **For ground-truth annotation → `junction_extend_n1`** (fewest over-merges + dangling
  to clean up by hand; under-connection is cheap to fix in CVAT).
- **Avoid ranking by `composite` alone** — it's over-merge-only and rewards
  under-connecting (see Metric caveat below).

Cycle any of these live in the UI **Join Check** tab (dropdown + balanced + verdict).

## What "joining" is (concept)

Detection gives a parts list + wires. Joining answers *"which component terminals
are electrically the same point?"* — grouping pins into **nodes (nets)**. The
output is a **netlist** (components + nets), which is what SPICE/simulation/redraw
need and what we want as paper ground truth. A node legitimately contains many
pins (that's a junction), so multi-pin nets are correct *in principle*.

## How the production join works (and where it breaks)

`core/netlist.py`:
1. `derive_pins_from_obb` — static pins from each component's box (≈30% connectivity alone).
2. `discover_pins` — DBSCAN-cluster wire endpoints near SPICE-active components to
   relocate pins onto real wire ends (≈100%+ connectivity). **Requires `scikit-learn`.**
3. `build_netlist` — for each wire, grab **all** pins within `max_pin_dist=30px` of
   **either** end and merge their nodes (union-find, transitive).

The breakage is step 3's rule: **all-within-30px + transitive merge** can't tell
"truly common (junction)" from "merely close (dense area)". One mislocated pin or
one false wire bridges two nets and the merge cascades. Documented failure modes:
dense areas (64% of mapping errors), junction confusion, "connectivity too permissive".

## How to verify (no ground truth needed)

### 1. Objective scorecard — `wire_detection/benchmark/netlist_validate.py`
Counts structural errors that are wrong by circuit laws. The **composite** (struct
errors / component, lower=better) is the regression number to track across changes.
```
uv run python wire_detection/benchmark/netlist_validate.py --obb-zip <downloaded_obb.zip>
```
Baseline (94-img batch, best_candidate_v4): self-loops 6.7%, floating 1.5%,
giant-nets 113, nets/component 0.09, **composite 0.1029**. A tighter radius
(`--max-pin-dist 18`) cut self-loops but exploded dangling/floating → composite
*worse* (0.1209): **no single global radius wins** — the fix must be structural.

### 2. Image-grounded views — `wire_detection/benchmark/netlist_viz.py`
Draws the joins **on the schematic** so you can check them against real copper:
- `<stem>_netlist.png` — all nets, color per net.
- `<stem>_joins.png` — all nets as real edges: **cyan**=wire, **green**=wire-end→nearest
  pin (intended), **orange**=extra pins the same end also grabbed (the over-joins).
- `--isolate <stem>` — a browsable **per-net stepper**: one net at a time, so you can
  verify a single net's terminals against the image.
```
uv run python wire_detection/benchmark/netlist_viz.py --obb-zip <zip>                 # all images, both overlays
uv run python wire_detection/benchmark/netlist_viz.py --obb-zip <zip> --isolate <STEM>  # per-net stepper
```

### 3. In the tuner UI — the **Join Check** tab
`/api/join_overlay` (route `wire_detection/api/routes/join_overlay.py`) renders the
same overlay server-side; the **Join Check** panel shows it with an "All nets" view
and a per-net selector/stepper. This is the verification view the UI previously
lacked (Topology is an abstract full-clique graph with no image; Netlist is a text
table). Use **Topology** to *spot* an over-merged net, **Join Check** to *prove*
which terminals shouldn't be in it.

> Reading the views: **green only, hugging copper = good join. Orange edges or a net
> spanning many far-apart components = over-merge.**

## The stages of joining (the pipeline)

Joining = turn (detected wires + component boxes) into electrical **nets**. It runs
in these stages; a "strategy" is a choice of method at one or more stages:

1. **Pin localization** — decide where each component's terminals (pins) are.
   Methods: static OBB geometry · DBSCAN-relocate to wire ends (SPICE-active only) ·
   *junction-aware* relocate for junctions/terminals too.
2. **Wire conditioning** — optionally fix the wires before attaching.
   Methods: none · *extend ends* by N px (occlusion-gap fix).
3. **Attach** — decide which pins each wire-end connects to.
   Methods: *all within radius* (production) · *nearest-k* · *anchored* (must reach
   the component) · *density-adaptive radius* · *mutual nearest-neighbour*.
4. **Merge** — union pins that share a wire into nodes (transitive union-find). This
   is fixed; the over-merge comes from stages 1+3 feeding it bad pairings.
5. **Cleanup (optional)** — post-process nodes: remove/split giant nets, enforce
   pin-count topology constraints. *(roadmap — not yet a strategy)*
6. **Score** — structural health (self-loops, floating, giant nets, dangling,
   nets/component, composite). No ground truth needed.

The registry in `core/join_strategies.py` composes choices at stages 1-3 into the
named strategies below.

## Current join strategy — step by step (verifiable)

Production path (`/api/netlist`, `/api/join_overlay` with `strategy=production`):

1. **Pins** (`core/netlist.py`): `derive_pins_from_obb` gives each component static
   pins from its OBB; `discover_pins` (DBSCAN on wire endpoints near SPICE-active
   parts) relocates those pins onto real wire ends. → `make_pins` in
   `core/join_strategies.py`.
2. **Attach + merge** (`build_netlist`, exposed as strategy `production`): for each
   wire, grab **every pin within 30px of *either* endpoint** and union their nodes
   (transitive). → nets = connected groups of pins.
3. **Score** with `score_netlist` (structural errors, no GT).

Verify it yourself: UI **Join Check** tab with strategy = *Production* (overlay +
metrics on the image), or `uv run python wire_detection/benchmark/netlist_validate.py --obb-zip <zip>`.

## Where it lacks

- **Multi-grab over-merge:** step 2 grabs *all* nearby pins, not the nearest, so dense
  areas/junctions fuse unrelated pins; transitive union-find then cascades.
- **Flat 30px radius:** too big in dense areas, too small where wires were truncated.
- **Pin localization:** static OBB pins are mislocated; clustering only runs for
  SPICE-active types, so junctions/terminals get poor pins → dangling + missed joins.
- **No anchor/topology check:** connectivity is pure proximity — it never asks "does
  the wire actually reach this component?" or "does a resistor have exactly 2 nets?".
- **No metric for it:** detection F1 doesn't measure any of this (see top of doc).

## ⚠ Metric caveat — composite is an OVER-merge detector only (verified)

**A lower composite did NOT mean better-looking joins**, and this was confirmed
visually: `mutual_30` had the *best* composite but its overlays look *sparse* — it
leaves much of the wiring unjoined. Why: the composite = (self-loops + floating +
giant)/components penalizes **over**-merge, but a strategy can drive all three terms
down simply by **not connecting** — `floating` only counts *fully* isolated
components, and net **fragmentation / missed wire→pin links are not penalized at all**.
So conservative strategies (`mutual`, `nearest1`) *game* the composite.

Fix: added **`unused_wires` / `pct_wires_used`** (wires that exist but joined nothing
= the under-connection the eye sees) and a **`balanced`** score
(`composite + 0.5·unused_wire_rate`). Sorting by `balanced` matches visual quality.
Both are shown in the UI Join Check metrics row, with an over-merge vs under-connect
**verdict** badge.

## FULL EVALUATION — all 1,648 images (fresh best_candidate_v4 detection)

`wire_detection/benchmark/join_eval_all.py` (1,648 images, 140,573 components). **Sorted by `balanced`** (the
eye-matching score). Note how `composite` and `balanced` disagree:

| rank | strategy | self-loop | floating | giant | wires-used% | composite | **balanced** |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | **nearest2_30** | 3817 | 10173 | 1832 | **86.1** | 0.1126 | **0.1855** ✅ |
| 2 | **junction_extend_n1** | 1064 | 13462 | 969 | 84.7 | 0.1102 | 0.1876 |
| 3 | extend12_n1_30 | 364 | 14792 | 895 | 82.7 | 0.1142 | 0.1919 |
| 4 | **production (current)** | 5821 | 7886 | 2197 | 76.4 | 0.1131 | 0.2358 |
| 5 | junction_n1_30 | 1303 | 15930 | 639 | 76.5 | 0.1271 | 0.2497 |
| 6 | anchored2_30 | 472 | 15623 | 1324 | 74.6 | 0.1239 | 0.2502 |
| 7 | nearest1_30 | 1501 | 14974 | 525 | 74.3 | 0.1209 | 0.2506 |
| 8 | density_30 | 1487 | 15096 | 509 | 73.6 | 0.1216 | 0.2549 |
| 9 | all_18 | 3751 | 12253 | 1655 | 72.0 | 0.1256 | 0.2834 |
| 10 | anchored1_30 | **26** | 17499 | 739 | 68.0 | 0.1299 | 0.2845 |
| 11 | **mutual_30** | 1689 | 9495 | **485** | **56.9** | **0.0830** | 0.3192 |
| 12 | nearest1_18 | 1373 | 17198 | 332 | 60.3 | 0.1345 | 0.3506 |

**Verdict (balanced — matches the eye):**
- **`mutual_30` "wins" on composite (0.083) but is 2nd-WORST on balanced (0.319)** — it
  uses only **56.9%** of wires. This is exactly the "better number, worse joins" effect:
  it scores well by under-connecting.
- **Best real strategies connect the most wires while limiting over-merge:**
  `nearest2_30` (86% wires used) and `junction_extend_n1` (85%, also lowest dangling).
  These look *and* score best.
- **Production is mid-pack (4th):** it over-merges (5821 shorts, 2197 giants) and still
  only uses 76% of wires.
- **Anchor/extend stages crush false shorts** (`anchored1` → 26, `extend12` → 364) but
  over-float → poor balanced.
- **Lesson:** never rank joins by an over-merge-only metric. Use `balanced` + the
  visual overlay. The true optimum is *connect most wires AND avoid over-merge*
  (nearest2 / junction+extend), not either extreme.

Reproduce: `uv run python wire_detection/benchmark/join_eval_all.py` (≈3 min for all images).

## Strategy catalog (registry: `core/join_strategies.py`, cycle in UI Join Check)

Same pins for every strategy; only the attach rule / radius / anchor changes. Batch
scorecard (94 images, 5434 components; lower composite = better, nets/comp ~0.5-1.0 healthy):

| strategy | what it changes | self-loop | floating | giant | nets/comp | **composite** |
|---|---|---:|---:|---:|---:|---:|
| **nearest1_30** | each end → nearest pin only | 89 | 307 | 91 | 0.18 | **0.0896** ✅ |
| nearest2_30 | ≤2 nearest per end | 249 | 124 | 128 | 0.11 | 0.0922 |
| anchored1_30 | nearest + must reach the pin's component bbox | **4** | 387 | 115 | 0.14 | 0.0931 |
| production | all pins within 30px (current) | 362 | 84 | 113 | 0.09 | 0.1029 |
| all_18 | production rule, 18px radius | 187 | 357 | 113 | 0.14 | 0.1209 |
| nearest1_18 | nearest only, 18px radius | 75 | 538 | 55 | 0.18 | 0.1229 |

**Findings:**
- **Multi-grab is a real over-merge cause:** nearest-only cut self-loop shorts
  362→89 and improved composite 0.103→0.090.
- **anchored1_30 nearly eliminates shorts (362→4)** by requiring the wire to actually
  reach the component — but leaves the most floating (387). Best when false shorts are
  the priority.
- **Not a full fix:** nets/component only reaches 0.18 (healthy ~0.5-1.0); giant nets
  persist → residual over-merge is junctions/cascades + pin localization, not the
  attach rule alone.
- **Trade-off:** nearest/anchored reduce shorts at the cost of floating (missed
  connections). For manual CVAT correction that's arguably a better start (add a missing
  wire vs. untangle a blob).
- **Tightening radius alone hurts** — no single global radius wins.

Reproduce the table: `uv run python wire_detection/benchmark/join_experiments.py --obb-zip <zip>`

## How to cycle & decide
- **UI → Join Check tab:** the **Join strategy** dropdown swaps strategies live; the
  metrics row (self-loops / floating / giant / nets/comp / **composite**) updates per
  strategy + image, and the overlay redraws. Use the **net selector** to verify
  individual nets. This is the "view and decide by metrics" loop.
- **CLI:** `wire_detection/benchmark/join_experiments.py` for the batch-wide composite ranking.
- The registry `core/join_strategies.py` is the **single source of truth** — adding a
  strategy there makes it appear in the UI dropdown, the API, and the CLI automatically.

## Improvement roadmap (stages, beyond the implemented attach-rule strategies)
Each is a separable stage; combine the winners.
1. **Pin localization (highest leverage):** cluster-discover pins for ALL component
   types incl. junctions/terminals; use OBB orientation. Most floating + dangling
   traces back here.
2. **Junction-aware joining:** model junctions/terminals as explicit multi-way nodes
   (a junction pin legitimately ties many wires) instead of relying on proximity.
3. **Density-adaptive radius:** shrink the attach radius where component density is high.
4. **Wire-end extension:** push truncated endpoints (occlusion gap) to the nearest
   component before attaching — kills dangling at component edges.
5. **Anchor/connectivity gate:** keep the `anchored` idea (wire must reach the
   component) but pair it with better pins so it doesn't inflate floating.
6. **Topology cleanup (post-merge):** split/flag nets via articulation points or
   degree limits; enforce known pin counts (resistor=2) to catch over/under-merge.
7. **Learned join:** train a classifier on (wire, pin) pairs once a little
   hand-labeled connectivity GT exists (the annotation effort this project is producing).

## Known issues / setup notes (Windows local)

- **Missing dependency:** `core/netlist.py` imports `sklearn` but `scikit-learn` is
  NOT in `pyproject.toml`. A clean `uv sync` leaves `/api/netlist` + `/api/join_overlay`
  crashing on import. Workaround used: `uv pip install scikit-learn` (venv only).
  **Fix: add `scikit-learn` to `pyproject.toml` dependencies.**
- **Pointing the UI at local batch data:** `load_component_labels` only matches the
  `hdc` dataset with filenames `<stem>.rf.*.txt`. To use local YOLO-OBB component
  labels, stage copies as `ui_data/hdc/train/labels/<stem>.rf.0.txt` and point a
  `DATASETS_YAML` at them (see `ui_data/datasets.yaml`). Launch backend with
  `DATASETS_YAML=...` env.
- **UI dev script is Unix-only:** `ui/package.json` `dev` uses `HOSTNAME=0.0.0.0 next…`
  which fails on Windows. Run `pnpm exec next dev -p 4200` instead (or switch the
  script to `cross-env`).
- **ngspice (for the Simulation tab) — WORKING.** ngspice 46 (`Spice64`) is copied to
  `ui_data/tools/Spice64`. The backend is launched with
  `NGSPICE_PATH=…/ui_data/tools/Spice64/bin/ngspice_con.exe`. **Use the console build
  `ngspice_con.exe`, not the GUI `ngspice.exe`** — the GUI build does not emit `-b`
  batch results to stdout. `core/simulator.py` now resolves ngspice via `NGSPICE_PATH`
  env → `ngspice_con` on PATH → `ngspice` on PATH. Verified: a voltage divider returns
  n1=5V, n2=2.5V.
  Note: simulation on an over-merged netlist with the generator's **default component
  values** (every R=1kΩ etc.) yields meaningless numbers — fix the joins first;
  simulation is not a join validator.
- **SPICE generation made simulatable.** The `/api/netlist` route used the basic
  `SpiceGenerator.generate()`, which emitted undefined diode models (`d1 n0 n0
  d_default`) and unknown subckts (`x1 …`) with no `.op` → ngspice aborted. `generate()`
  now: emits `.model` defs for diodes/transistors, skips devices with no SPICE model
  (IC/opamp/junction/terminal/fuse/switch — listed in a `* skipped` comment), adds
  `.options rshunt=1e12` so the DC op stays solvable despite over-merge, and ends with
  `.op`. Verified: real images now return an operating point (`success=True`).

## Where experiments / tests are recorded (this repo)
- `docs/join-verification.md` — **this file** (join experiments log, above).
- `docs/autonomous-experimentation-log.md` — running log of automated experiments.
- `docs/iteration-tracker.md` — iteration-by-iteration progress.
- `docs/*-synthesis.md` — `complete-netlist-exploration-synthesis`,
  `connectivity-filter-synthesis`, `netlist-exploration-synthesis`,
  `mapping-experiment-synthesis` (final write-ups per investigation).
- `docs/connectivity.md`, `docs/expanded-benchmark.md` — method comparison tables.
- `output/<experiment>/…json` — raw per-run metrics written by the benchmark scripts
  (e.g. `experiment_harness.py`, `connectivity_experiment.py`).
- `paper/` — the LaTeX write-up + tables for publication.

## Endpoint-graph join — a better connectivity model (not just a tuned attach rule)

All strategies above share one structural limit: the join graph has **only component
pins as nodes; wires are edges** that merge the pins near both ends. That cannot
represent **wire-to-wire** connectivity (T-junctions, rails/buses, collinear
fragments) — a wire that reaches no pin connects nothing — and it over-merges via
all-to-all grabbing. The `junction`-pin hack only helps where a *labeled* junction
component happens to sit.

`wire_detection/core/join_graph.py` replaces the model: **both wire endpoints AND
pins are graph nodes**, with five edge types —
1. wire body (ep1–ep2),
2. endpoint↔endpoint within `tau_join` (fragments, junctions, corners),
3. endpoint↔pin, nearest within `tau_pin`, optionally **directional** (bind the pin
   the wire *points at*, not merely the closest),
4. endpoint↔wire-body within `tau_t` (**T-junction** onto a rail/bus),
5. pin↔wire-body within `tau_t` (a component **tapped onto a passing rail**).

Nets = connected components of {pins ∪ endpoints}, projected onto pins. Tolerances can
be **scale-relative** (`k × median component size`, clamped to [floor, cap]) so one
rule fits the ~6× circuit-scale range. Registered strategies: `graph_30`,
`graph_dir_30`, `graph_scale`, `graph_full` (scale-relative + directional + extend).

**Metric fix.** `balanced` rewards raw wire-use, so the endpoint graph can *game* it by
chaining wires together without reaching components (`used%`=100 while `conn%`=0).
`score_netlist` now also returns **`pct_effective_wires`** (wires in a net spanning ≥2
distinct components — not gameable) and **`join_quality`** = composite over-merge +
under-connection penalty by *effective* wires. **Rank joins by `join_quality`.**

**Dead-end rescue.** A wire firmly anchored at ONE end (its net spans exactly one
component) but dangling at the other is almost always a real connection the *detector*
cut short (e.g. a resistor→inductor wire captured only halfway, free end stopping 55px
short — beyond the normal reach). `graph_rescue` gives just those free ends a longer,
DIRECTIONAL reach (`rescue_factor × tau_pin`) toward a pin on a different component. The
one-anchor evidence + forward-direction gate keep it from re-introducing over-merge.

**Result (60 HDC images, fixed baseline detection, median):**

| strategy | join_quality | conn% | eff% | giant | self |
|---|---|---|---|---|---|
| **graph_rescue** | **0.126** | **84** | 100 | 1.0 | 2.5 |
| graph_full | 0.131 | 76 | 97 | 1.0 | 2.5 |
| junction_extend_n1 | 0.137 | 67 | 87 | 0.0 | 0.0 |
| nearest2_30 | 0.163 | 75 | 91 | 1.0 | 2.0 |
| production (current) | 0.222 | 81 | 80 | 1.0 | 2.0 |

`graph_rescue` **beats production on 53 / 58 images (ties 3, loses 2)** and now exceeds
production's connectivity (`conn%` 84 vs 81) with **100% effective wires** — while
keeping the clean structure (no over-join shorts). The 2 losses are detection-starved
images (≈1–5 wires for a large circuit) where no join can connect components the detector
never produced. Verify in the **Join Check** tab by selecting `graph_rescue` (auto-listed).

WHY wires still get excluded (e.g. images C115_D1_P2/P3): the join keeps a wire only if
it bridges ≥2 component pins. An excluded wire is anchored on one pin but its other end
falls short of the next pin (detection cut the wire), beyond the join's reach. `graph_rescue`
recovers these; what remains is detection-limited (no wire was produced at all).

## Files added by this investigation (repo root unless noted)
- `wire_detection/core/join_graph.py` — endpoint-graph join (5 edge types, scale-relative).
- `join_compare.py` (local) — rank every strategy by `join_quality` on fixed detection.
- `wire_detection/benchmark/netlist_viz.py` — image-grounded join overlays + per-net stepper.
- `wire_detection/benchmark/netlist_validate.py` — structural join-health scorecard.
- `wire_detection/benchmark/join_experiments.py` — attach-rule strategy comparison (Exp 1 above).
- `make_netlist_pdf.py` — bundle overlays into a shareable PDF.
- `wire_detection/api/routes/join_overlay.py` — `/api/join_overlay` endpoint.
- `wire_detection/api/models.py` — `JoinOverlayRequest` (added).
- `wire_detection/core/simulator.py` — ngspice resolver (NGSPICE_PATH / ngspice_con).
- `ui/src/components/JoinCheckPanel.tsx` + wiring in `HomeClient.tsx`, `actions.ts`,
  `lib/types.ts` — the **Join Check** UI tab.
