# Circuit Digitization Tuner UI

Interactive web UI for the circuit-digitization pipeline. It sits on top of the
Python backend and lets you step through images, inspect the detected topology,
edit wire connections by hand, and see how those edits propagate to the netlist
and simulation.

Built with Next.js 16 and React 19, managed with pnpm.

## Features

- **Topology view** — an SVG overlay on the source image showing detected wires,
  pins, components, and electrical nodes, coloured by net.
- **Connection editor** — a docked panel for hand-editing wire connections.
  Manual edits are stored as per-image overrides (`reassign` / `join` / `remove`)
  that the backend bakes into the netlist as node merges.
- **Join-check / dead-end signals** — wire endpoints and component pins that
  dangle are flagged (red endpoint dots, amber pin rings), with a Quick Fix
  action to auto-connect to the nearest valid pin.
- **Netlist and simulation overlays** — the resulting SPICE netlist, voltages,
  and currents update to reflect your edits.
- **Dataset deep-linking** — `?ds=` and `?idx=` select the dataset and image.

## Prerequisites

The UI is a front end for the pipeline backend, so start that first, from the
repository root:

```bash
# Download the model weights (one-time)
uv run python scripts/download_model.py

# Start the tuner backend
uv run wire-tune
```

## Getting Started

From this `ui/` directory:

```bash
pnpm install
pnpm dev
```

Then open [http://localhost:4200](http://localhost:4200).

Same-origin `/api` requests are rewritten to the backend in `next.config.ts`, so
no additional proxy configuration is needed.

## More

See the [root README](../README.md) for the full pipeline, datasets, and
benchmark documentation.
