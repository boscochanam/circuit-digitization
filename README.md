# Wire Detection Framework

A modular Python framework for detecting wires in circuit schematics — classical CV pipeline, synthetic data generator, evaluation toolkit, FastAPI backend, and Next.js tuner UI.

> **Full documentation at [https://boscochanam.github.io/circuit-digitization](https://boscochanam.github.io/circuit-digitization)** — or build locally with `uv run mkdocs serve`.

## Quickstart

```bash
uv venv && uv sync          # Backend setup
cd ui && pnpm install       # Frontend setup
docker compose up --build   # Or: uv run wire-tune + pnpm dev
```

## CLI

```
wire-tune      Start the tuner API server
wire-pipeline  Run pipeline on a single image
wire-sdg       Generate synthetic dataset
wire-eval      Evaluate detections against ground truth
wire-sweep     Run a parameter sweep
```

## Project Structure

```
wire_detection/     Python backend (pipeline, API, SDG, evaluation, experiments)
ui/                 Next.js frontend (tuner UI)
docs/               MkDocs documentation
```

## Development

```bash
uv run pytest wire_detection/tests/ -q   # Tests
uv run mypy wire_detection/              # Types
uv run ruff check wire_detection/        # Lint
```

## License

See [LICENSE.txt](LICENSE.txt).
