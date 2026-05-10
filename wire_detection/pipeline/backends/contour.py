from typing import Any
import numpy as np
from wire_detection.pipeline.backends.registry import PipelineBackend, register_backend
from wire_detection.pipeline.factory import PipelineFactory


class ContourBackend(PipelineBackend):
    def run(self, image: np.ndarray, params: dict[str, Any]) -> dict[str, Any]:
        config = params.get("config", {})
        pipeline = PipelineFactory.from_config(config)
        result = pipeline.run(image)
        return {
            "lines": result.lines,
            "raw_lines": result.raw_lines,
            "blob_count": result.blob_count,
            "elapsed_ms": result.elapsed_ms,
        }


register_backend("contour", ContourBackend)
