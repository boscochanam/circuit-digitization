# Backends

The framework supports pluggable detection backends via the `PipelineBackend` interface. This allows comparing different detection approaches (classical CV, YOLO, external repositories) using the same evaluation pipeline and metrics.

## Interface

```python
from abc import ABC, abstractmethod

class PipelineBackend(ABC):
    @abstractmethod
    def run(self, image: np.ndarray, params: dict) -> PipelineResult: ...
```

## Available Backends

### Contour (Default)

The built-in 9-stage CV pipeline. This is the default and primary backend. See [Pipeline Overview](overview.md).

```python
from wire_detection.pipeline.backends.contour import ContourBackend

backend = ContourBackend()
result = backend.run(image, params)
```

### SINA

Wraps the CCL-based net discovery approach from Aldowaish et al. (arXiv:2601.22114) for benchmarking comparison.

The SINA approach masks components, runs CCL on remaining wires, and treats each CCL region as an electrical net. It produces blobs rather than individual wire segments.

```python
from wire_detection.pipeline.backends.sina import SINABackend

backend = SINABackend()
result = backend.run(image, params)
```

## Custom Backend

To add a new backend, implement the interface and register it:

```python
from wire_detection.pipeline.registry import register_backend

class MyBackend(PipelineBackend):
    def run(self, image, params):
        lines = my_detection_function(image, params)
        return PipelineResult(
            lines=lines,
            raw_lines=lines,
            blob_count=0,
            stage_outputs={},
            params_used=params,
            elapsed_ms=0.0,
        )

register_backend("my_backend", MyBackend)
```

Once registered, the backend is available in the experiment engine and CLI:

```bash
wire-eval --backend my_backend --dataset hand_drawn
```
