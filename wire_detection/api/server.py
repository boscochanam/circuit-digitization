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

from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.pipeline.registry import STAGES
from wire_detection.data.dataset import DatasetRegistry
from wire_detection.api.cache import ImageCache


def _ensure_synthetic_data():
    registry = DatasetRegistry()
    cfg = registry.get("synthetic")
    if cfg is None or not cfg.path.exists():
        return
    existing = list(cfg.path.glob("images/*.jpg"))
    if len(existing) >= 50:
        return
    from wire_detection.sdg.generator import SDG, SDGConfig
    print(f"Generating synthetic dataset at {cfg.path}...")
    sdg = SDG(SDGConfig(
        num_images=50,
        seed=42,
        image_size=(256, 256),
        output_dir=cfg.path,
        label_format="lines",
        wires_per_image=(3, 8),
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
def list_images(ds: str = Query("hand_drawn")):
    images = registry.list_images(ds)
    return JSONResponse([str(p.name) for p in images])


@app.get("/api/thumb")
def get_thumb(idx: int = 0, ds: str = Query("hand_drawn")):
    images = registry.list_images(ds)
    if idx < 0 or idx >= len(images):
        return JSONResponse({"error": f"index {idx} out of range (0-{len(images)-1})"}, status_code=404)
    try:
        path = str(images[idx])
        img = cache.load_image(path, resize=80)
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
    ds = data.get("ds", "hand_drawn")
    params = data.get("params", {})

    images = registry.list_images(ds)
    if img_idx < 0 or img_idx >= len(images):
        return JSONResponse({"error": "index out of range"}, status_code=404)

    try:
        image = cache.load_image(str(images[img_idx]))
    except FileNotFoundError:
        return JSONResponse({"error": "image not found"}, status_code=404)

    config = {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
        "stage_params": {
            "threshold": {
                "mode": params.get("thresh_mode", "otsu"),
                "value": int(params.get("thresh_val", 127)),
                "block_size": int(params.get("block_size", 31)),
                "c": int(params.get("c", 2)),
            },
            "dilate": {
                "kernel_size": int(params.get("dil_ksize", 5)),
                "iterations": int(params.get("dil_iters", 1)),
            },
            "ccl": {
                "min_area": int(params.get("min_area", 30)),
            },
            "dedup": {
                "angle_thresh": int(params.get("dedup_angle", 10)),
                "dist_thresh": int(params.get("dedup_dist", 12)),
            },
            "length_filter": {
                "min_length": int(params.get("min_line_length", 0)),
            },
        },
    }

    pipeline = PipelineFactory.from_config(config)
    result = pipeline.run(image)

    overlay = pipeline.visualize(image, result)

    return JSONResponse({
        "line_count": len(result.lines),
        "blob_count": result.blob_count,
        "elapsed_ms": result.elapsed_ms,
        "overlay": _img_to_base64(overlay),
        "threshold": _img_to_base64(result.stage_outputs.get("threshold", image)),
        "dilated": _img_to_base64(result.stage_outputs.get("dilated", image)),
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
