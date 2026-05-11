# Development

## Setup

```bash
# Clone and install
git clone <repo>
cd LineDetection
uv venv && uv sync

# Install pre-commit (optional)
uv run pre-commit install
```

## Running Tests

```bash
# All tests
uv run pytest wire_detection/tests/ -q

# With coverage
uv run pytest wire_detection/tests/ --cov=wire_detection

# Specific test file
uv run pytest wire_detection/tests/test_pipeline.py -v
```

## Code Quality

```bash
# Type checking
uv run mypy wire_detection/

# Linting
uv run ruff check wire_detection/

# Formatting
uv run ruff format wire_detection/
```

## Project Structure

```
wire_detection/
├── pipeline/        # Detection pipeline (stages/, backends/, core, factory)
├── api/             # FastAPI server (routes, cache, server)
├── data/            # Dataset registry (dataset, transforms)
├── sdg/             # Synthetic data generator (generator, primitives, backgrounds)
├── evaluate/        # Evaluation (metric, match, report, visualize)
├── experiment/      # Sweep engine (sweep, runner, reporter, presets)
├── config/          # Dataset YAML configs
└── tests/           # Tests (pipeline, sdg, evaluate, integration)

ui/
├── src/
│   ├── app/         # Next.js App Router pages
│   ├── components/  # React components (sidebar, grid, picker, etc.)
│   └── lib/         # API client, utils
└── public/          # Static assets
```

## Adding a Pipeline Stage

1. Create a new file in `wire_detection/pipeline/stages/`
2. Implement the `PipelineStage` ABC
3. Decorate with `@register_stage("name")`
4. The stage is automatically discovered and available in the UI

```python
from wire_detection.pipeline.registry import register_stage
from wire_detection.pipeline.types import PipelineStage, StageOutput

@register_stage("my_stage")
class MyStage(PipelineStage):
    name = "my_stage"

    def run(self, image, params):
        # Process image
        return StageOutput(data=result, visualization=vis)

    def visualize(self, image, output):
        return vis_image
```

## Documentation

This documentation is built with [MkDocs](https://www.mkdocs.org/):

```bash
# Serve locally
uv run mkdocs serve

# Build static site
uv run mkdocs build
```
