# Synthetic ground-truth evaluation for the join + SPICE pipeline

**Status:** first working slice landed (`wire_detection/synthgt/`). Error model is
a placeholder pending calibration (see Roadmap).

## The idea

So far we evaluate the pipeline by taking a *real* hand-drawn image, running the
detector, then **manually** repairing the fragmented result in the UI until SPICE
can simulate it. That proves SPICE works on one circuit at a time, but it is slow,
needs a human in the loop, and gives us no net-level ground truth to score the
**join** against (issue [#20]).

This runs the loop the other way:

```
author a known-good circuit (netlist + values)         <- we control the truth
        |
        v
lay it out as a 2-D coordinate map (component bboxes + wires)
        |
        v
inject detector-style error (jitter / cut-short / drop)   <- the placeholder bit
        |
        v
run the REAL join + REAL SPICE on those coordinates
        |
        v
score vs the netlist we started from
```

Because we authored the netlist, we get two things for free, at scale:

1. **Net-level ground truth for the join** — directly closes the [#20] gap. We
   score component-connectivity F1 (did the join tie together exactly the
   components the authored netlist ties together).
2. **A SPICE oracle** — the authored circuit has a known operating point, so we
   can assert the simulation is right without a human checking it.

## What this validates well — and what it doesn't

This was thought through before building it; the honest scope:

**Strong:**
- **SPICE / "is the simulator doing its job":** excellent. We author a valid
  netlist, so the expected operating point is known and asserted. The harness
  confirms `I_src` for every catalog circuit matches the analytic value —
  including the diode drop (4.307 mA simulated vs 4.31 mA computed from the
  DMOD equation) and the opposing two-source loop (exactly 1 mA). An authoring
  guard flags any spec whose oracle disagrees with its `expect_mA`.
- **Join *logic* + regression:** good. Known target → perturb → measure recovery.
  Catches regressions on cases that *should* be easy, and gives robustness curves.

**Gaps (do not over-read the join numbers):**
- **Error-model fidelity is everything.** Real detection error is *structured and
  correlated with the image* (breaks at faint strokes / crossings, anchor
  over-deletion [#21], junction-vs-crossing confusion [#19]). The placeholder here
  is uniform jitter + symmetric cut-short + independent drops + uniform wrong-pin
  snaps — a clean IID model the real detector does **not** have. Until it is
  calibrated, synthetic join scores predict robustness *to this noise*, not
  real-image performance.
- **Over-merge is exercised, but uncalibrated.** The `wrong_pin` error mode snaps
  an endpoint onto a nearby pin it does not belong to, so precision now moves
  (without it the model could only break wires and precision sat at a meaningless
  1.00). The *rate and locality* of that confusion are invented numbers, though —
  same calibration caveat as above.
- **Topology distribution.** Authored circuits skew textbook; real hand-drawn
  ones have a long tail. Ground the catalog in real netlists (below) to fix this.
  Related: synthetic maps contain **no junction/terminal symbols**, so the
  junction-aware join modes are never exercised here.
- **It sidesteps detection — the actual bottleneck.** The loop starts *after*
  detection (netlist -> coordinates), so it says nothing about why real circuits
  arrive fragmented ([#21]). It measures join + sim, not detection.
- **A single cross-net short is invisible to DC sim.** One extra wire is not a
  return path, so it doesn't change operating-point currents — `sim_ok` won't
  catch it. That is *why* join precision is scored separately; the `dense_pair`
  circuit (two independent loops side by side) exists to bait exactly this.

The SPICE half stands on its own. The join half is a scaffold that becomes
trustworthy only once the error model and the circuit distribution are anchored
to reality.

## The harness

`wire_detection/synthgt/`:

| file | role |
|---|---|
| `circuits.py` | `CircuitSpec` + a catalog of authored circuits with clean layouts: parallel/series/ring resistor loops, R–L, a forward-biased **diode**, a **gnd**-referenced divider (node-0 remap), an opposing **two-source** loop, and `dense_pair` (two independent loops — the over-merge bait). |
| `synthesize.py` | `CircuitSpec` -> components + wires (routed to real pin positions); plus the **placeholder error model** (`ERROR_LEVELS`, `inject_errors`): jitter, cut-short, drop, and the wrong-pin snap (over-merge). |
| `evaluate.py` | runs the real join + SPICE, scores join (component-pair F1) and sim (operating-point match across **every** authored source, injected-source count). Also flags spec-authoring bugs (oracle vs `expect_mA` mismatch) and takes a `strategy=` to compare joins. |
| `__main__.py` | CLI report. |

Run it:

```bash
# full suite (needs ngspice for the SPICE columns; set NGSPICE_PATH)
uv run python -m wire_detection.synthgt
uv run python -m wire_detection.synthgt -c ring6_r -s 16        # one circuit, more seeds
uv run python -m wire_detection.synthgt --strategy production   # score one join strategy
uv run python -m wire_detection.synthgt --compare              # rank EVERY join strategy
uv run python -m wire_detection.synthgt --json > out.json
```

## Using it to test implementations

**Test the current join strategies, all at once** — `--compare` runs every
strategy in the registry against the whole catalog and prints a ground-truth
leaderboard (join-only, so it's fast):

```
strategy                clean     L1     L2     L3     L4   mean(err)
graph_full             1.00  1.00  0.98  0.96  0.89     0.958
graph_rescue           1.00  1.00  0.98  0.96  0.89     0.958
...
production             1.00  1.00  0.98  0.89  0.50     0.843
mutual_30              0.92  0.94  0.91  0.80  0.44     0.773  <-- fails clean
all_18                 1.00  1.00  0.91  0.47  0.17     0.637
```

This already earns its keep: the flagship graph joins top the board, the legacy
`nearest`/`production` family collapses at heavy error, and `mutual_30` is
flagged because it cannot recover even the **clean** control (it under-merges) —
a correctness bug surfaced by ground truth, not a structural proxy.

**Test a future implementation** is the same loop with zero new wiring:
1. Add the new strategy to the registry (`wire_detection/core/join_strategies.py`).
   It appears in `--compare` automatically (the CLI reads `list_strategies()`).
2. `uv run python -m wire_detection.synthgt --compare` — see where it ranks; if
   its `clean` column is < 1.0 it is broken on easy cases, full stop.
3. `--strategy <name>` for the per-circuit / per-severity breakdown + SPICE.

**Test a change to the join/SPICE internals** (not a new strategy):
1. `uv run pytest wire_detection/tests/test_synthgt.py` — the invariants
   (clean F1 = 1.0, oracle == authored expectation, recall non-increasing) fail
   if the change regressed correctness.
2. `--json > before.json` on `main`, apply the change, `--json > after.json`,
   diff — any moved number is a behaviour change to explain.

Metrics per error level (averaged over seeds):
- **F1 / recall / precision** — component-connectivity vs ground truth. Recall
  down = fragmentation / under-merge; precision down = shorts / over-merge.
- **sim_ok** — % of seeds where **every** authored source's branch current
  matches the clean oracle (within 2%) with **no** injected test source.
  Checking all sources matters: a multi-source circuit can fragment *between*
  its sources and each island still "works" locally.
- **inj** — mean fake sources the backend injected to energize disconnected
  islands; a direct fragmentation-magnitude readout.

The harness asserts every **clean** (level 0) join recovers F1 = 1.0; a failure
there flags a bad layout or a join regression, not a noise effect.
`wire_detection/tests/test_synthgt.py` locks this invariant in.

## Strategy selection: why graph_rescue (a worked example)

The harness was used to pick the default join empirically rather than by intuition.
`--compare` over the 15-circuit catalog ranks the `graph_*` family (with the
component-first endpoint binding) at ~0.94-0.96 mean-error F1, while the legacy
`nearest`/`mutual`/`anchored`/`production` families collapse to 0.48-0.76 and
several fail the clean control. Within the graph family the differences are small,
so reach-tuned variants were tried (dead-end reach 2.2x -> 2.8x / 3.5x, end
extension 12px -> 20px, directional on/off):

- **More reach is a wash.** The 2.2x rescue already reaches ~132px, past the 80px
  max anchor-displacement, so longer reach recovers nothing extra (per-circuit
  precision/recall are identical to graph_rescue).
- **`extend=20` regresses** — it over-reaches on clean layouts and grabs the wrong
  pin, breaking the F1 = 1.0 invariant (a real over-merge, caught by the harness).
- The residual high-error failures are **recall drops from wires dropped entirely**
  (a detection loss, [#21]) — unrecoverable by any join. The join is at its ceiling.

Conclusion within the *existing* registry: `graph_rescue` is the best of the
shipped algorithms. But the harness can also be used as a SEARCH ENGINE for new
ones (next section), and that did turn up a winner.

## Strategy search: a candidate that beats graph_rescue

Using the ground truth as a search target (ideate diverse families -> implement +
score each vs ground truth -> adversarially verify the winners), one candidate
genuinely beat `graph_rescue`:

**`degree_budget_completion`** (`wire_detection/synthgt/candidate_joins.py`) — a
post-processing COMPLETION layer on top of graph_rescue. A pin whose net touches
only its own component is "floating" (the signature of a dropped/over-displaced
wire); it reconnects such pins to other components via reach-bounded **min-cost
b-matching** (at most one edge per floating pin). Scores (12 seeds, 15 circuits):

```
join                       clean   L1     L2     L3     L4   mean(err)  wheatL3p
graph_rescue (baseline)    1.00  1.00  0.97  0.94  0.87    0.944      0.885
degree_budget_completion   1.00  1.00  0.99  0.96  0.94    0.972      0.921
```

It wins at every severity (+0.035 mean-error F1), keeps clean = 1.0, and RAISES
bridge precision — it is not a precision-for-recall trade. Run it with
`uv run python -m wire_detection.synthgt --candidates`.

**Adversarial verification (overfit_risk = low):** the gain is stable across seed
batches (0.972 at 12 seeds, 0.9705 at 24), the REACH_FACTOR sweep is smooth (not a
tuned spike), and the win is concentrated in DROP mode (recovering wires the
detector missed entirely — a real high-frequency failure) where precision *rises*.
Contrast: a second apparent winner (`candidate_join_ilp_relaxation`, 0.951) was
verified as **overfit** — its headline number was the luckiest seed batch, its
named ILP mechanism was inert, and it regressed on jitter mode. The adversarial
pass is what separated the real win from the artifact.

A robust secondary finding: ~10 other candidates beat graph_rescue on bridge
*precision* (0.92–0.97) but lost *recall* at high severity — graph_rescue is
recall-optimized, and the drop-heavy error model rewards that. Only
`degree_budget_completion` improved recall on drops without sacrificing precision.

**Promotion (done):** the two production blockers from the real benchmark were
fixed — a self-loop guard (one pin per component per net) and wire tracking (base
wires carried onto final nodes) — then validated on **real images** (40-image
subset, gt153 + hdc): self-loops 4.4 → **1.38** (below graph_rescue's 1.82), wire
coverage 0% → **83%**, connectivity **+16.5%** with *fewer* floating components.
The implementation was moved to `wire_detection/core/completion.py`, registered as
the `degree_budget` join strategy, and is now `DEFAULT_STRATEGY`; graph_rescue
stays as fallback (`?strategy=graph_rescue`). **Residual caveat:** the connectivity
gain still has no net-level ground truth ([#20]) to fully rule out over-merge —
but real self-loops *and* floating components both dropped, which is consistent
with recovering real connections, not inventing them. Confirm on the full
153-image set; recheck once the error model is calibrated ([#61], [#62]).

## Roadmap (to make the join numbers trustworthy)

1. **Calibrate the error model to the real detector.** Run the detector on the
   manually-verified images, diff its wire/endpoint output against the verified
   truth, and fit the actual statistics: cut-short distribution, endpoint-
   displacement spread, break rate, and junction/crossing + wrong-pin confusion
   rates. Replace `ERROR_LEVELS` / `inject_errors` with samplers from those
   fits. (The error *modes* — including the over-merge wrong-pin snap — exist;
   their *rates* are invented.)
2. **Ground the topology in reality.** Generate the authored netlists by
   reverse-engineering the manually-verified circuits (the UI's human-verified
   connectivity is exactly this ground truth) instead of hand-writing textbook
   loops — realistic component mix and layout distribution. Synthesize
   junction/terminal symbols too, so the junction-aware join modes get exercised.
3. **Keep a real-image holdout.** Synthetic for scale / tuning / regression;
   the manually-verified set as the source of truth. Report both; if they
   diverge, the error model is wrong — fix it, don't trust the synthetic.
4. ~~Widen the catalog~~ **partially done:** diode, gnd-referenced, multi-source,
   and adjacent-loops (`dense_pair`) circuits landed. Still missing:
   transistors, junction symbols, and genuinely dense layouts where the join
   must choose between nearby pins of *connected* nets.

The manual-UI work is the feeder for steps 2–3, not a competitor to this: it is
how human-verified ground truth gets minted cheaply (the completeness indicator
and pin-to-pin connect make producing it fast).

[#19]: https://github.com/boscochanam/circuit-digitization/issues/19
[#20]: https://github.com/boscochanam/circuit-digitization/issues/20
[#21]: https://github.com/boscochanam/circuit-digitization/issues/21
[#61]: https://github.com/boscochanam/circuit-digitization/issues/61
