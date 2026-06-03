# Why wires "disappear" and don't connect on the HDC dataset

Investigation of the report: *"many in the HDC dataset, the detected lines disappear
and it's not present and connected."*

**Headline:** the symptom is framed as a *joining* problem, but the evidence shows
**most of the loss happens upstream of the join** — detection drops the wires before
the join ever sees them. There are three distinct failure modes (A and B are
detection, C is the join) sitting on top of one cross-cutting root cause (no scale
normalization).

All numbers below are from a 50-image stratified sample of the 1680 HDC images, run
through the exact UI/API path (`_run_preset_pipeline` → `detect_wires_experiment`,
preset `best_candidate_v4`). Repro scripts: `hdc_detect_diag.py` (stage survival),
`hdc_fixes_probe.py` (intervention test). Overlays dumped to `ui_data/diag/`.

The HDC images are **raw phone photos** of hand-drawn circuits (paper on a desk, at an
angle), resized to 704×704 — *identical* files to `manually_verified_no_background_data`
(the "no background" name is a misnomer; there is a background). The 0.83 F1 is an
**average**; browsing the set surfaces the failure tail the average hides.

---

## Aggregate signal (n=50)

| Metric | Value | Reading |
|---|---|---|
| Component labels load | 50/50 | **Not** a label/component problem |
| Foreground after threshold | median **2.0%**, min **0.4%** | Strokes barely survive binarization |
| Lines, anchor filter ON | median 22.5, min 2 | — |
| Lines, anchor filter OFF | median 29.5 | Anchor filter removes ~24% median |
| Anchor deletes **>40%** of lines | **11/50 images** | Over-deletion is common, not rare |
| Join `used < 60%` | **8/50 images** | Under-connection tail |
| Crop ratio (circuit/frame) | 16% … 98% | **~6× scale variance** |

---

## Mode A — faint strokes lost at binarization  (DETECTION)

**What you see:** light-pencil / washed-out circuits where the overlay shows 4–6
lines and the rest of the drawing is simply not traced. Anchor ON == OFF, so the
filter is *not* the cause — the strokes never make it through thresholding.

**Why:** a single global Sauvola threshold (k=0.285, w=67) tuned for darker ink, then
`close kernel=3` and `CCL min_area=28`, drop faint/broken thin fragments. Foreground
density falls to 0.4–0.8% — there is almost nothing left to extract.

**Examples:** C1_D1_P1 (fg 0.5%, 5 lines), C20, C39, C64, C279.

**Verified fix** (CLAHE contrast + k=0.15 + min_area=12 + close=5):

| image | baseline | faint-fix | note |
|---|---|---|---|
| C1_D1_P1 | 5 | **37** | plain paper — recovered wires are all real (clean) |
| C64_D1_P4 | 6 | **39** | graph paper — recovers wires **but also lights up grid** |
| C20 / C39 / C279 | 4–6 | 13–15 | recovered |

See `ui_data/diag/fix_C1_*` (clean recovery) vs `fix_C64_*` (grid false-positives).

**Caveat:** the same aggressive recovery that's a clean 7× win on plain paper amplifies
**graph/lined-paper grids** into false wires. The recovery must be paired with
background/grid suppression, or gated on background type.

---

## Mode B — anchor filter over-deletes real wires  (DETECTION, post-filter)

**What you see:** detection finds the wires, then most of them vanish — long rails and
junction wires especially.

**Why:** `filter_component_connected_lines` keeps a wire only if an **endpoint** is
within `anchor_endpoint_dist=12px` of a component port, or it links within
`anchor_link_dist=8px` to such a wire. That model is wrong for:
- **rails / buses** — endpoints sit at the corners of the schematic, far from any port;
  they connect mid-span via T-junctions.
- **junction-to-junction wires** — connect two other wires, not a component.
- hand-drawn gaps **larger than 8px** between a wire and its neighbour.

So real structural wires get orphaned and deleted. This hits **11/50 images >40%**.

**Examples (lines ON vs OFF):** C77 9 vs 38, C152 5 vs 20, C54 2 vs 10, C162 34 vs 61,
C132 13 vs 31.

**Verified fix** (relax to endpoint=24, link=20 — keeps a filter, just widens reach):

| image | baseline (12/8) | relax (24/20) | off |
|---|---|---|---|
| C77_D2_P1 | 9 | **30** | 38 |
| C152_D1_P1 | 5 | **15** | 20 |
| C162_D2_P3 | 34 | **59** | 61 |
| C54 / C132 | 2 / 13 | 6 / 30 | 10 / 31 |

`ui_data/diag/fix_C77_*` confirms the recovered green lines are genuine rails/verticals,
not noise. Relaxing recovers ~75–80% of what fully-off recovers while retaining noise
rejection — but the *right* fix is a junction-aware filter (below), not just bigger numbers.

---

## Mode C — join under-connects  (CONNECTION)

**What you see:** wires are detected but float — not wired into a net.

**Why:** the production join grabs pins within a fixed **30px** of a wire end. On
fragmented hand-drawn endpoints and on large/dense circuits the true pin is >30px away,
so the wire stays floating. `used<60%` on 8/50; worst C77 0%, C64 33%, C162 38%. Dense
circuits (C247 321 components, C241 255, C265 215) carry the most floating nets.
This is the same fixed-radius brittleness documented in `join-verification.md`
(production over-merges *and* under-connects depending on scale).

---

## Root cause underneath all three — no scale normalization  (Mode D)

Every threshold in the pipeline is an **absolute pixel value**: Sauvola window 67,
CCL min_area 28, dedup 18, anchor 12/8, join 30. But the circuit's scale varies **~6×**
across HDC (crop ratio 16%→98% of a 704px frame; component counts 12→321).

- **Small circuit in a big frame** → wires are physically tiny → faint strokes lost,
  fragments below min_area.
- **Large / dense circuit** → anchor 12px is relatively microscopic → rails orphaned;
  join 30px too small → under-connection.

A single fixed parameter set cannot fit all scales. This is why one preset that scores
0.83 on average still fails hard on a large minority.

---

## Edge-case catalogue (with example IDs)

| Edge case | Effect | Examples |
|---|---|---|
| Faint / light pencil, under-exposed | strokes lost at threshold (Mode A) | C1, C20, C39, C279 |
| Graph / grid / lined paper | grid competes with strokes; CLAHE amplifies it | C64, C152 |
| Long rails / buses | endpoints far from ports → anchor deletes (Mode B) | C77, C152 |
| Junction-to-junction wires | no component endpoint → anchor deletes (Mode B) | C54, C162 |
| Dense circuits (100s of components) | fixed thresholds mis-scaled → floating nets (C) | C247, C241, C265 |
| Small circuit in large frame (crop <25%) | physically tiny wires | C64, C282, C279 |
| Perspective skew / tilted paper / shadow | non-axis-aligned strokes, uneven lighting | C100 |

---

## Recommended approaches (ranked by impact × confidence)

1. **Adaptive faint-stroke recovery (Mode A).** CLAHE + lower k + lower min_area +
   bigger close, **gated on measured foreground density** (apply only when fg < ~1.5%).
   Verified 6–7× line recovery on plain paper. *Highest impact.*
2. **Background/grid suppression (Mode A caveat).** Detect periodic grid (FFT notch or
   morphological long-line removal) and subtract before threshold, so #1 doesn't
   manufacture grid wires. Unlocks #1 safely on graph paper.
3. **Junction-aware anchor filter (Mode B).** Keep a wire if it's connected — through
   the wire-to-wire graph — to *any* anchored wire, not only if its own endpoint touches
   a port. (Connected-component reasoning over wires+anchors together.) Falls back to the
   relaxed 24/20 distances if a rewrite is too much. Verified recovery of real rails.
4. **Scale normalization (Mode D, cross-cutting).** Estimate circuit scale (median
   component size or stroke width) and express every pixel threshold relative to it — or
   resize the cropped ROI to a canonical resolution before detection. Makes all the other
   parameters robust at once. Highest leverage, most invasive.
5. **Scale-relative join radius (Mode C).** Replace fixed 30px with a function of median
   component spacing; combine with endpoint-extension (the existing `extend12` strategy)
   to bridge fragmented ends to pins.
6. **Threshold fusion (Mode A robustness).** The harness already supports voting across
   Sauvola+Otsu+adaptive (`threshold_fusion_enabled`); enable to catch strokes any single
   method misses.

**Suggested first step:** ship #1+#2 as an opt-in "faint/raw recovery" preset and a UI
toggle, evaluate on all 1680 with the existing harness (precision must not crater on grid
paper), then take #3 and #4 as their own changes. #5 plugs into the existing strategy
registry.

---

## Recovery tooling — built & measured

The fixes are implemented as an ordered, **cumulative** set of iterations so each one
can be viewed and chosen independently:

- `wire_detection/core/recovery.py` — the iteration registry (0 baseline → 5 fusion),
  `grid_suppress()` (FFT notch), and `diff_lines()` (added/kept/removed classifier).
- `wire_detection/api/routes/recovery.py` — `/api/recovery_overlay` (runs every
  iteration, returns per-iteration proxy metrics + a diff-highlighted overlay:
  **blue kept · green added · red removed**) and `/api/recovery_iterations`.
- UI **Recovery** panel (`ui/src/components/RecoveryPanel.tsx`) — iteration stepper,
  "highlight vs previous/baseline" toggle, and a metrics table (click a row to view).
- `recovery_eval.py` (local, untracked) — batch metrics + iteration-ladder montages.

### Batch metrics (40-image HDC sample)

| iteration | med lines | vs base | med used% | mean ink% | recovers on | floods (ink>20) |
|---|---|---|---|---|---|---|
| 0 Baseline | 20 | +0 | 72 | 2.4 | — | 0/40 |
| 1 +Contrast (CLAHE) | 34 | +14 | 72 | 4.7 | 30/40 | 0/40 |
| 2 +Faint threshold | 32 | +12 | 67 | 8.1 | 29/40 | 2/40 |
| 3 +Grid suppress | 46 | +27 | 56 | 13.2 | 30/40 | 9/40 |
| 4 +Junction anchor | 66 | +46 | 40 | 13.2 | 38/40 | 9/40 |
| 5 +Threshold fusion | 66 | +46 | 40 | 53.1 | 38/40 | 39/40 |

**Conclusions from the numbers:**
- **+Contrast (CLAHE) is the safe default** — +14 lines median, recovers on 30/40,
  *zero* flooding, join metric unchanged. Highest value-per-risk.
- **+Junction anchor = maximum recall** (+46) but `used%` falls 72→40: recovering
  detection **exposes the fixed-radius join** (Mode C). Aggressive recovery must be
  paired with a scale-relative join.
- **+Grid suppress** helps graph paper but still floods 9/40 at aggressive thresholds —
  the FFT notch needs strengthening before #4 is safe on grids.
- **+Threshold fusion is strictly harmful** here — no extra lines over #4, floods 39/40
  (Otsu union saturates faint images). **Drop it.**

The per-iteration ladder montages (`ui_data/diag/ladder_*.png`) show, in green, exactly
what each step adds: e.g. C1 (faint, plain) `5→18→37→40→46→46`; C152 (graph paper)
`5→3→8→20→74→74` where the jump to 74 is visibly grid false-positives.

## How detection feeds the join — and how to get good joins from detected lines

The join turns lines into a netlist like this:

```
detected wires ──► derive pins (component terminals + junctions)
              └──► for each wire END, attach to nearby pins   ← the STRATEGY decides
                          which pins / how many / how far / extend?
              └──► union-find merges pins that share a wire ──► nets
```

So **detected wires are the edges of the connectivity graph** and pins are the nodes.
A wire only creates a connection if **both its endpoints land near the right pins**.
That makes join quality a function of three line properties: coverage (is the wire
there at all), endpoint accuracy (does the end reach the terminal), and spurious lines
(false edges → shorts).

**Why more lines ≠ better joins.** Recovered wires are often fragmented/short, so their
ends fall outside the fixed 30px attach radius and stay floating — `used%` *drops* as
detection recovers more (82%→50%, baseline→anchor). Detection recovery **exposes** the
join; the two must be tuned together.

### Joint experiment (25 images × 4 detection levels × 6 strategies)

`join_x_detect_eval.py` detects at each recovery level then scores every strategy.
Median **balanced** (lower = better; over-merge + under-connection):

| strategy | baseline | contrast | faint | anchor |
|---|---|---|---|---|
| production (current) | 0.234 | 0.197 | 0.239 | 0.380 |
| nearest2_30 | 0.189 | 0.139 | 0.160 | 0.319 |
| extend12_n1_30 | 0.172 | 0.155 | 0.142 | 0.336 |
| **junction_extend_n1** | **0.155** | **0.132** | **0.138** | **0.305** |

Best strategy at **every** detection level is **`junction_extend_n1`** (junction-aware
pins + endpoint extension + nearest-1). Best *pairing* overall is **moderate detection
(contrast/faint) + junction_extend** — balanced 0.132–0.138, used 85–92%, connected
75–80% — versus the shipped **baseline+production** (0.234, 82%, 60%). Pushing detection
to **anchor** *without* upgrading the join makes it worse (used 50%, balanced 0.305): the
fixed 30px can't connect the flood.

### The levers that make a join tolerant of imperfect lines
1. **Endpoint extension** — extend a wire-end a few px along its axis to reach a terminal
   the stroke fell short of. (the `extend` strategies)
2. **Junction-awareness** — let wires connect to *other wires* (rails, T-junctions), not
   only component pins. (the `junction` pins)
3. **Nearest-k attach** — bind to the 1–2 nearest pins, not ALL within radius (kills the
   production over-merge).
4. **Scale-relative radius** — 30px is absolute but circuits vary ~6× in scale; the radius
   should scale with component size. This is what unlocks the high-recall (anchor) regime.

**Recipe for good joins from detected lines:** detect with moderate recovery (CLAHE) →
join with `junction_extend_n1` → add scale-relative radius to use the extra recall.
(Proxy metrics — no GT nets — so confirm visually in the Join Check panel.)

## What this is *not*

- Not a missing-labels problem (components load 50/50).
- Not primarily a join problem — the join is Mode C only; A+B (detection) dominate the
  "disappear" symptom.
- Not fixed by join-strategy tuning alone — if detection never produced the wire, no
  strategy can connect it.
