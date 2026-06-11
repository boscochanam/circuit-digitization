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
uv run python -m wire_detection.synthgt --strategy production   # compare a join strategy
uv run python -m wire_detection.synthgt --json > out.json
```

The `--strategy` sweep is already informative: on the 6-component ring at heavy
error, the old `production` join scores F1 0.84 vs `graph_rescue`'s 0.90 — the
flagship's robustness advantage, now measured against ground truth instead of
structural proxies.

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
