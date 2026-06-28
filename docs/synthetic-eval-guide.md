# Synthetic Evaluation, Visualization & Simulation

How to use the synthetic ground-truth system to test, validate, and visualize the join + SPICE pipeline.

## Quick Start

```bash
# Run full evaluation (all 12 circuits × 8 seeds × 5 error levels)
uv run python -m wire_detection.synthgt

# Single circuit, more seeds
uv run python -m wire_detection.synthgt -c ring6_r -s 16

# Compare all join strategies
uv run python -m wire_detection.synthgt --compare

# JSON output for diffing
uv run python -m wire_detection.synthgt --json > out.json

# Generate 3-panel visualizations for all circuits
uv run python docs/draw_3panel.py
```

Default join strategy is **`scale_completion`** (`DEFAULT_STRATEGY`, promoted Jun 2026). Seed
guidance: the cross-strategy leaderboard uses **8 seeds**; the per-circuit deep-dive uses
**16 seeds** (e.g. `-s 16`).

## Architecture

### Synthetic Data Pipeline

```
CircuitSpec (authored netlist + layout)
    │
    ▼
synthesize_clean() → components + wires (clean coordinates)
    │
    ▼
inject_errors(error_level, seed) → perturbed wires
    │
    ▼
run_strategy("scale_completion", err_wires, components) → Netlist  # DEFAULT_STRATEGY
    │
    ▼
Score: component-pair F1 vs ground truth
```

### Circuit Catalog (`wire_detection/synthgt/circuits.py`)

12 authored circuits with known netlists:

| # | Name | Components | Nets | Topology |
|---|------|-----------|------|----------|
| 0 | `parallel_rr` | 6 | 3 | Two parallel resistor pairs |
| 1 | `divider_rr` | 6 | 4 | Series voltage divider |
| 2 | `loop4_r` | 4 | 2 | Simple 4-resistor loop |
| 3 | `rl_series` | 4 | 2 | R-L series (L shorts at DC) |
| 4 | `ring6_r` | 6 | 3 | 6-resistor ring |
| 5 | `diode_r` | 3 | 2 | Forward-biased diode |
| 6 | `gnd_ref` | 4 | 2 | Ground-referenced divider |
| 7 | `two_sources` | 4 | 2 | Opposing voltage sources |
| 8 | `angled_v` | 5 | 3 | V-shape with angles |
| 9 | `dense_pair` | 6 | 2 | Two independent loops (over-merge bait) |
| 10 | `angled_ring4` | 4 | 2 | Diamond with rotated components |
| 11 | `angled_parallel` | 4 | 2 | Parallel paths, all angled |

### Error Model (`wire_detection/synthgt/synthesize.py`)

5 error levels (L0–L4) with increasing severity:

- **L0 (clean)**: No errors — asserts F1=1.0 for all strategies
- **L1–L2**: Mild perturbation — endpoint jitter, slight compression
- **L3**: Moderate — significant displacement, some wire compression
- **L4**: Severe — heavy compression, anchor deletion, wrong-pin snaps

Error modes:
- **Endpoint jitter**: Random displacement of wire endpoints
- **Wire compression**: Endpoints move inward, shrinking wire length
- **Anchor deletion**: Endpoints displaced 30–80px from target
- **Wrong-pin snap**: Endpoint snaps to incorrect nearby pin (over-merge)

**Important**: The error model is a placeholder. Real detection error is structured and correlated with the image. Synthetic join scores measure robustness to this noise, not real-image performance.

### Shared Component Assignment (`wire_detection/core/component_assignment.py`)

The **single source of truth** for assigning wire endpoints to components and pins:

```
endpoint → nearest component (within assignment radius) → pin (by position along long axis)
```

Assignment radius: `max(tau_pin, 0.5 × diagonal)` — e.g., a component with diagonal=301px gets radius=150.7px.

**This is the only place that does endpoint→component→pin assignment.** All other code (pipeline, visualization) imports from here.

### Netlist (`wire_detection/core/netlist.py`)

The `Netlist` class is the canonical representation of circuit connectivity:

- `pin_to_node`: maps `(component_idx, pin_name)` → `node_id`
- `nodes`: list of `NetNode`, each with `pins` and `wire_indices`
- `wire_connects_components(wire_idx)`: checks if a wire joins two different components
- `connected_wires()`: returns set of all wire indices that connect components

## Visualization

### 3-Panel (`docs/draw_3panel.py`)

The primary visualization. For each circuit, shows three stages side-by-side:

1. **Ground Truth** (green) — clean wires, correct connections
2. **Error Injected** (red) — perturbed wire positions
3. **After Join** (blue/orange) — algorithm recovery, wires snapped to actual pin positions

Each circuit gets its own file: `docs/synthgt_3panel_{name}.png`

Features:
- Circuit ID `[N]` in title for easy reference
- Wire labels (W0, W1, ...) at midpoints
- Yellow dots at pin positions
- Connected wires snap to actual pin positions (not error-injected positions)
- F1/P/R scores annotated

**Rules for adding new visualizations:**
1. Use `net.wire_connects_components()` or `net.connected_wires()` — never reimplement connection checks
2. Snap connected wire endpoints to actual pin positions, not raw error-injected positions
3. See `.hermes-agent` for the full rule set

### Other Visualizations

| File | Purpose |
|------|---------|
| `draw_join_eval.py` | Eval grid: multiple circuits × error levels, colored by recovery |
| `draw_join_demo.py` | Side-by-side: ground truth → detected → joined |
| `draw_error_grid.py` | Error level grid with F1 scores per circuit |
| `draw_error_sweep.py` | Error level progression for key circuits |
| `draw_circuits_v4.py` | Circuit catalog reference images |

All visualization files use the shared `Netlist` class for connection status. None reimplement bbox checks or endpoint proximity logic.

## Scoring

### Join Score (Component-Pair F1)

Compares which components the algorithm connects vs the ground truth netlist:

- **Recall**: fraction of ground-truth component pairs recovered
- **Precision**: fraction of algorithm's pairs that are correct
- **F1**: harmonic mean

L0 (clean) must always give F1=1.0 — a failure there flags a layout bug or join regression.

### SPICE Score

Verifies simulation matches the authored circuit's known operating point:

- Checks branch currents against analytic values
- Flags injected test sources (indicates fragmentation)
- `sim_ok` = all sources match clean oracle within 2%

## Testing Changes

### New Join Strategy

1. Add to registry in `wire_detection/core/join_strategies.py`
2. `uv run python -m wire_detection.synthgt --compare` — see ranking
3. `--strategy <name>` for per-circuit breakdown + SPICE

### Join/SPICE Internals

1. `uv run pytest wire_detection/tests/test_synthgt.py` — invariant checks
2. `--json > before.json`, apply change, `--json > after.json`, diff

### Visualization Changes

1. `uv run python docs/draw_3panel.py` — regenerate all
2. Verify L0 (clean) panels show all wires blue (recovered)
3. Check that connected wires snap to pin positions, not raw endpoints
