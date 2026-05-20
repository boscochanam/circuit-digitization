import os
from pathlib import Path
from typing import Any
import base64
import cv2
import numpy as np
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from io import BytesIO
import yaml

from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.pipeline.registry import STAGES
from wire_detection.data.dataset import DatasetRegistry
from wire_detection.api.cache import ImageCache


def _load_default_config():
    """Load pipeline config from defaults.yaml."""
    pkg_dir = Path(__file__).resolve().parent.parent
    defaults_path = pkg_dir / "config" / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            return yaml.safe_load(f)
    # Fallback
    return {
        "stages": ["crop", "mask", "threshold", "invert", "close", "ccl", "contour_extract", "dedup"],
        "stage_params": {
            "crop": {"padding": 10},
            "mask": {"fill_value": 255, "occlusion_margin": 0.15},
            "threshold": {"mode": "sauvola", "k": 0.30, "window": 51},
            "close": {"kernel_size": 3, "shape": "ellipse"},
            "ccl": {"min_area": 20},
            "dedup": {"angle_thresh": 10, "dist_thresh": 18},
        },
    }


def _ensure_synthetic_data():
    registry = DatasetRegistry()
    cfg = registry.get("synthetic")
    if cfg is None:
        return
    cfg.path.mkdir(parents=True, exist_ok=True)
    existing = registry.list_images("synthetic")
    if len(existing) >= 50:
        return
    from wire_detection.sdg.generator import SDG, SDGConfig
    parts = cfg.image_glob.split("/")
    try:
        img_idx = parts.index("images")
        subdir = "/".join(parts[:img_idx])
        output_dir = cfg.path / subdir if subdir else cfg.path
    except ValueError:
        output_dir = cfg.path
    print(f"Generating synthetic dataset at {output_dir}...")
    sdg = SDG(SDGConfig(
        num_images=50,
        seed=42,
        image_size=(640, 640),
        output_dir=output_dir,
        label_format=cfg.label_format or "lines",
        components_count=(4, 8),
        components_size=(50, 130),
    ))
    sdg.generate()
    print("Synthetic dataset generated.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_synthetic_data()
    yield


app = FastAPI(title="Wire Detection Tuner", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = DatasetRegistry()
cache = ImageCache()


def _img_to_base64(image: np.ndarray) -> str:
    _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


@app.get("/api/list")
def list_images(ds: str = Query("gt_labels")):
    images = registry.list_images(ds)
    return JSONResponse([str(p.name) for p in images])


@app.get("/api/thumb")
def get_thumb(idx: int = 0, ds: str = Query("gt_labels")):
    images = registry.list_images(ds)
    if idx < 0 or idx >= len(images):
        return JSONResponse({"error": f"index {idx} out of range (0-{len(images)-1})"}, status_code=404)
    try:
        path = str(images[idx])
        img = cache.load_image(path, resize=300)
        _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return StreamingResponse(BytesIO(buffer.tobytes()), media_type="image/jpeg")
    except FileNotFoundError:
        return JSONResponse({"error": "image not found"}, status_code=404)


@app.get("/api/datasets")
def list_datasets():
    info = {}
    for key in registry.list_datasets():
        cfg = registry.get(key)
        images = registry.list_images(key)
        info[key] = {
            "path": str(cfg.path) if cfg else None,
            "images": len(images),
            "sample": str(images[0]) if images else None,
        }
    return JSONResponse(info)


@app.post("/api/process")
def process_image(data: dict[str, Any]):
    img_idx = data.get("img_idx", 0)
    ds = data.get("ds", "gt_labels")
    params = data.get("params", {})

    images = registry.list_images(ds)
    if img_idx < 0 or img_idx >= len(images):
        return JSONResponse({"error": "index out of range"}, status_code=404)

    try:
        image = cache.load_image(str(images[img_idx]))
    except FileNotFoundError:
        return JSONResponse({"error": "image not found"}, status_code=404)

    # Load default config and apply UI param overrides
    config = _load_default_config()
    stage_params = config.get("stage_params", {})

    # Apply UI overrides
    if "k" in params:
        stage_params["threshold"]["k"] = float(params["k"])
    if "min_area" in params:
        stage_params["ccl"]["min_area"] = int(params["min_area"])
    if "dedup_angle" in params:
        stage_params["dedup"]["angle_thresh"] = int(params["dedup_angle"])
    if "dedup_dist" in params:
        stage_params["dedup"]["dist_thresh"] = int(params["dedup_dist"])
    if "close_ks" in params:
        stage_params["close"]["kernel_size"] = int(params["close_ks"])

    pipeline = PipelineFactory.from_config(config)
    result = pipeline.run(image)

    overlay = pipeline.visualize(image, result)

    return JSONResponse({
        "line_count": len(result.lines),
        "blob_count": result.blob_count,
        "elapsed_ms": result.elapsed_ms,
        "overlay": _img_to_base64(overlay),
        "threshold": _img_to_base64(result.stage_outputs.get("threshold", image)),
        "close": _img_to_base64(result.stage_outputs.get("close", image)),
    })


@app.get("/api/stages")
def list_stages():
    return JSONResponse(list(STAGES.keys()))


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("<html><body><h1>Wire Detection API</h1><p>Use /api/ endpoints.</p></body></html>")


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
