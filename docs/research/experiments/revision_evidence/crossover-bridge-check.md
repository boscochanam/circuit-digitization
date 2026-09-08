# Crossover-blind endpoint graph: empirical bridge check on the 31-image benchmark

**Question:** Does `build_endpoint_graph` (wire_detection/core/join_graph.py) ever actually
bridge two GT-independent nets across a `crossover` symbol on the 31-image human-verified
benchmark, given that its edge types 2/4/5 use pure point-to-segment/point-to-point geometry
over wires with no reference to component class?

**Verdict up front:** **REAL BUG, CONFIRMED on 1 of 31 images** (`C242_D1_P1_jpg`), via a
causal ablation (not just proximity correlation). Two other images had crossover-adjacent
geometric edges that looked suspicious under a proximity heuristic but were shown, by the same
ablation, **not** to be the cause of their false-merges. 5 of 8 crossover-containing images had
**no geometric edge at all** near the crossover. See section 3 for the precise scope of this claim.

---

## 1. Data layout summary

- **Class id.** `roboflow_test2/data.yaml:11` → `5: crossover`. Confirmed against
  `wire_detection/core/component_classes.py:13` (`5: "crossover"`).
- **31-image GT** (`ground_truth/real_nets_verified.json`) stores only SPICE-active
  ("electrical") components in its `components`/`electrical_idxs` fields (checked: the full set
  of `type` values across all 31 entries contains no `"crossover"`, `"junction"`, `"terminal"`,
  etc. — only R/C/L/D/Q/IC/voltage types). So **crossover instances are not in the net-GT JSON
  at all**; they must be recovered from the underlying YOLO-OBB component labels
  (`roboflow_test2/{train,valid,test}/labels/*.txt`, class id 5), located via
  `wire_detection/benchmark/build_net_gt.find_hdc_label()` /
  `wire_detection/benchmark.build_net_gt.parse_components()` (same lookup the eval scripts use).
  `/home/claw/workspace/ground_truth/labels_few_annot/` holds the human-traced GT **wire**
  labels + source images (`GT_WIRE_LABELS`, `GT_IMAGES` in `build_net_gt.py:53-61`), not
  component OBB labels — crossovers live only in `roboflow_test2/*/labels`.
- **No stored recovered-net artifacts exist anywhere in the repo.** Checked
  `docs/research/experiments/*.json` and `ground_truth/*.json`: every file is an aggregate
  score (tp/fp/fn/F1 per image/strategy), never the actual recovered `pin_to_node` mapping.
  `wire_detection/benchmark/join_eval_real_f1.py` has no `--dump-nets` (or equivalent) flag —
  it computes `comp_pairs()` (line 38-47) in memory and discards the netlist object after
  scoring (see the `run_strategy(...)` call at line 101 — `nl` is used only to build `pred` and
  then dropped). **Getting real recovered nets without editing the repo requires calling the
  same library functions (`detect_wires`, `run_strategy`) directly from a throwaway script** —
  which is what this investigation did (below), not modifying any repo file.
- `docs/research/experiments/join_micro_n31.json` per-image entries include a `scale_completion`
  block (tp/fp/fn/F1) even though `join_eval_real_f1.py`'s own default `STRATEGIES` list (line 35)
  is `["degree_budget", "graph_rescue", "graph_scale", "production"]` — so that JSON must have
  been produced with `--strategies` overridden to include `scale_completion`, the current
  `DEFAULT_STRATEGY` (`join_strategies.py:384`). Used here to cross-check FP counts.

**Key code-path finding (static):** `build_endpoint_graph()` (`join_graph.py:98-317`) has no
parameter or lookup that references `components[i][0]` (class id) or `COMPONENT_TYPES` for edge
types 2 (`join_graph.py:143-152`), 4 (`210-220`), or 5 (`222-231`) — confirmed by reading the
full function body; the only components-aware step is edge 3's pin-binding
(`154-208`, via `assign_endpoint_to_component`), which is about *which pin* a wire-end binds to,
not *whether crossing wires should bridge*. The literal string `"crossover"` never appears in
`join_graph.py` or `completion.py`. It appears only in `join_strategies.py:63` (`INERT_TYPES`,
used solely by `score_netlist`'s floating-component accounting) and `join_strategies.py:143`
(`_JUNCTION_TYPES`, used only by `make_pins_junction_aware`, which **none of the default/flagship
strategies use** — `degree_budget`, `graph_rescue`, `graph_scale`, `scale_completion` all call
`make_pins()`, not the junction-aware variant; see `join_strategies.py:443-453`). So the audit's
premise is confirmed exactly: the flagship join has zero crossover-awareness in its bridging
edges. Also worth noting for context: `real_nets_verified.json` GT nets were originally
*bootstrapped* by running `graph_scale` (the same crossover-blind endpoint graph) over
perfect human-traced wires and then human-corrected (`build_net_gt.py:8-14, 68-73`) — so the
GT-construction process shares the exact same blind spot; a residual risk (not evaluated here)
is that a human reviewer could have missed an over-merge at a crossover during that
verification pass and frozen it into "ground truth."

## 2. Per-image crossover bridge table

8 of the 31 images contain ≥1 GT crossover component (13 crossover instances total). For each,
wires were **detected** with the real pipeline detector (`detect_wires`, same as
`join_eval_real_f1.py`), pins built with `make_pins`, and the netlist built with the **flagship
default strategy `scale_completion`** (`degree_budget_completion(base="scale", reach_factor=4.0,
relax_witness=True)`, which internally calls `build_endpoint_graph` with the scale-relative
`graph_scale` tolerances). A geometric scan located every type-2/4/5 edge whose triggering
location (endpoint-endpoint midpoint / T-junction landing point) fell within
`crossover_bbox_radius + tau_t` of the crossover's bbox center. Where such edges existed, a
**causal ablation** re-ran the identical strategy with only those specific crossover-adjacent
edges suppressed (implemented in a throwaway `/tmp` script that patches
`completion.build_endpoint_graph`; repo untouched) and checked whether the image's false-merge
(FP) component pairs disappeared.

| image | #crossovers | geometric edge near crossover? | FP pairs (scale_completion) | ablation: ¬crossover-edges → FP pairs | causally caused by crossover? | scale_completion F1 (tp/fp/fn) |
|---|---|---|---|---|---|---|
| C22_D2_P3_jpg | 1 | no (no type-2/4/5 edge lands within tolerance of the crossover center) | (0,9), (1,9) | — (not tested; no candidate edge) | **No** | 0.884 (19/2/3) |
| C29_D2_P4_jpg | 1 | no | (2,3), (2,8) | — | **No** | 0.812 (13/2/4) |
| C15_D2_P2_jpg | 1 | no | (3,4), (5,8) | — | **No** | 0.889 (16/2/2) |
| C21_D1_P3_jpg | 1 | no | (1,2), (2,4), (2,5), (2,8) | — | **No** | 0.732 (15/4/7) |
| C19_D1_P2_jpg | 1 | no | (2,4), (2,6), (4,8), (5,7), (6,8), (7,8) | — | **No** | 0.866 (29/6/3) |
| **C112_D1_P1_jpg** | 1 | **yes** — 2 type-2 edges (wires 8/12/15, dist 7.8–9.9px) land ~5–20px from the crossover center (464,268) | (23,27) | **(23,27) still present** — unchanged | **No** — 23 & 27 are bridged into the same 7-component blob (`[15,18,20,23,24,25,27]`) via a *different, non-crossover* path; suppressing the crossover-adjacent edges left the blob identical | 0.976 (20/1/0) |
| **C242_D1_P1_jpg** | 1 | **yes** — 2 type-2 edges (wires 7/25/40, dist 5.8–8.1px) land ~6–19px from the crossover center (460,363) | (0,83), (30,83), (52,83), (82,83) | **empty `[]`** — all 4 FP pairs vanish | **YES — confirmed** | 0.931 (27/4/0) |
| **C66_D2_P4_jpg** | 6 | **yes** — 24 type-2 edges across all 6 crossover centers | (5,54), (6,54) | **(5,54), (6,54) unchanged** | **No** — the crossover-bridged node (`[1,44,45,50,57]`) contains neither component 5, 6, nor 54; it is in fact a *correct* merge (no pair within it is FP) — this is a legitimate rail/bus continuing past several crossover markers, not an over-merge | 0.771 (27/2/14) |

## 3. Aggregate verdict

- **8/31 images (26%)** contain a GT crossover component (13 crossover instances total).
- **3/8** of those images had a geometric type-2/4/5 edge land near a crossover at all
  (C112, C242, C66); the other 5 crossovers were geometrically inert — no bridging edge ever
  formed near them (the two crossing wires' fragments were far enough apart, or not fragmented
  at the crossing at all).
- Of those 3, causal ablation shows:
  - **1 confirmed real bug**: `C242_D1_P1_jpg` — the crossover-blind endpoint-endpoint edge
    (type 2) is the *sole* cause of 4 false component-pair merges (`(0,83)`, `(30,83)`,
    `(52,83)`, `(82,83)`), which GT keeps in disjoint nets (`83` is in GT nets 4/5; `0`,`30`,`52`,
    `82` are in GT nets 0/1). Removing only the crossover-adjacent edges eliminates every one of
    those FPs with no other change.
  - **2 false leads**: C112 and C66 both have geometrically-real crossover-adjacent bridging
    edges, but ablation shows those specific edges are **not** the cause of that image's FP
    pairs — C112's over-merge persists through an unrelated path, and C66's crossover-bridged
    blob is actually correct (matches GT; the FP pairs there involve unrelated components).

**"REAL BUG on 1 image out of 31" (out of 8 images that contain a crossover at all, i.e. 1/8 =
12.5% of crossover-bearing images, 3.2% of the full benchmark).** The mechanism described in the
audit is real, reproducible, and mechanically exactly as predicted (an endpoint-endpoint union
formed from wire-fragment stubs clustered at the crossing point, blind to the crossover symbol
that says those two lines must NOT connect) — but it is **not the systematic failure mode** one
might fear from reading `build_endpoint_graph` in isolation. It fires only when wire detection
happens to fragment *both* crossing wires with stub endpoints landing within `tau_join`
(scale-relative, floor 11px) of each other at the crossing point, which the data shows is
uncommon (3/13 crossover instances triggered any bridging geometry, 1/13 caused an actual
GT-violating merge).

## 4. The real instance: `C242_D1_P1_jpg`

- Crossover component idx 78, bbox `(457,358)-(463,368)`, center `(460, 363)`.
- Detected wires at that location (`detect_wires` output, pixel coords):
  - wire 40: `(432,364)-(456,364)` — horizontal, arriving from the left, stub end at `(456,364)`.
  - wire 25: `(460,319)-(460,357)` — vertical, arriving from above, stub end at `(460,357)`.
  - wire 7: `(459,369)-(458,428)` — vertical, departing downward, stub end at `(459,369)`.
- All three stub endpoints land within ~5.8–9.9px of each other, under `tau_join` (11px,
  scale-relative floor) — `join_graph.py:143-152` unions them via `uf.union(ekey(wi,ei),
  ekey(wj,ej))` at line 152, no component-class check anywhere in that loop.
- Effect: the horizontal wire (feeding component 83, a diode at (284,204), GT nets 4/5) gets
  unioned with the vertical wires (feeding components 0/30/52/82, GT nets 0/1) — precisely the
  "wire A passes over wire B without connecting" case a crossover marks, but the join treats it
  as one meeting point.
- Recommended response for the paper's reviewer reply (R2-4): **disclose as a known, empirically
  rare limitation**, not silently omit or claim it doesn't happen. Suggested phrasing: "The
  endpoint-graph join is class-agnostic; on the 31-image verified benchmark it produces a
  confirmed crossover false-merge on 1 image (a fragmented crossing where both wires' detector
  stubs land within the join tolerance of each other), out of 8 images containing a crossover
  symbol (13 instances). A straightforward mitigation — excluding wire stubs that fall inside a
  detected `crossover` component's bbox from edge types 2/4/5, or requiring the two wires'
  directions be roughly collinear before unioning stub endpoints — would close this gap; we have
  not implemented or benchmarked it." If reviewer pressure is high, implementing the "skip stubs
  inside a crossover bbox" filter is a small, targeted, low-risk change to `join_graph.py`'s edge
  2/4 loops (would need `components` passed with class ids, currently not used in those loops) —
  but that is a code change outside the scope of this read-only investigation.

## 5. Runtime note

- All analysis used the real pipeline's `detect_wires` (classical CV, not an ML model — cheap)
  and `run_strategy("scale_completion", ...)` / `degree_budget_completion` called directly from
  throwaway scripts in `/tmp` (`/tmp/find_crossovers.py`, `/tmp/find_crossovers2.py`,
  `/tmp/find_crossovers3.py`, `/tmp/find_crossovers4.py`, `/tmp/join_graph_ablate.py` — a
  parameterized copy of `build_endpoint_graph` with a `blocked_zones` ablation hook, used only to
  test causality, never to alter repo behavior). No repo file was modified. No retraining or
  detector-model invocation occurred.
- Total wall time across all 4 script runs: ~7 seconds (well inside the ~20-minute budget). No
  run approached the time limit; nothing was skipped for cost reasons.
- **Caveats on the method:**
  1. The "near-crossover" search radius (`bbox_radius + tau_t + margin`) is a reasonable but
     not-exact proxy for "this edge is physically at the crossing" — mitigated by the causal
     ablation, which directly tests removal of exactly those edges rather than relying on
     proximity alone.
  2. Attribution used the *actual* final-netlist `node.wires` mapping (not a nearest-pin guess)
     to confirm which wires end up on which final node — this is exact, not approximate.
  3. This check covers only the `scale_completion` (current default/flagship) strategy. Other
     registered strategies (`graph_rescue`, `graph_scale`, `degree_budget`) share the same
     crossover-blind `build_endpoint_graph` core and would likely show the same qualitative
     pattern (rare but real), but were not separately re-verified here.
  4. The GT itself (`real_nets_verified.json`) was bootstrapped using the same crossover-blind
     algorithm before human correction (see section 1); if a human reviewer missed a
     crossover-caused over-merge during that verification, this analysis — which trusts
     `real_nets_verified.json` as ground truth — would not detect it. No evidence either way was
     found; flagged as a residual risk, not a finding.
  5. A more definitive answer (e.g., exact rate across all strategies, or on a larger image set)
     would require either (a) a `--dump-nets` flag added to `join_eval_real_f1.py` to persist
     per-image recovered netlists for offline analysis at scale, or (b) rerunning this same
     ablation methodology per strategy — both cheap but out of scope for a read-only check.
