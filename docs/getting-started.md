# Getting Started

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Node.js 20+ and pnpm (for the frontend)

## Datasets

Before running the framework, you need datasets. See [Dataset Setup](datasets.md) for download and configuration instructions.

## Backend Setup

```bash
# Create virtual environment and install dependencies
uv venv && uv sync

# Run the API server
uv run wire-tune
```

The server starts on `http://localhost:8000`.

## Frontend Setup

In a separate terminal:

```bash
cd ui
pnpm install
pnpm dev
```

The frontend starts on `http://localhost:3000` and proxies API requests to the backend.

## Docker (Both Services)

```bash
docker compose down && docker compose up --build
```

## Verify Installation

```bash
# Run tests
uv run pytest wire_detection/tests/ -q

# List available pipeline stages
curl http://localhost:8000/api/stages

# List datasets
curl http://localhost:8000/api/datasets
```

## Next Steps

- Explore the [pipeline stages](pipeline/stages.md)
- Try the [interactive tuner](http://localhost:3000)
- Generate [synthetic data](sdg.md) for experimentation
- Run an [evaluation](evaluate.md) on the hand-drawn dataset
