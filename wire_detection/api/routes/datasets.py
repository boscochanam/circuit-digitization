"""Dataset and image API routes."""
from __future__ import annotations

import cv2
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO

import wire_detection.api.deps as deps

router = APIRouter()


@router.get("/api/list")
def list_images(ds: str = Query("gt_labels")):
    images = deps.registry.list_images(ds)
    return JSONResponse([str(p.name) for p in images])


@router.get("/api/thumb")
def get_thumb(idx: int = 0, ds: str = Query("gt_labels")):
    images = deps.registry.list_images(ds)
    if idx < 0 or idx >= len(images):
        return JSONResponse({"error": f"index {idx} out of range (0-{len(images)-1})"}, status_code=404)
    try:
        path = str(images[idx])
        img = deps.cache.load_image(path, resize=800)
        _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return StreamingResponse(BytesIO(buffer.tobytes()), media_type="image/jpeg")
    except FileNotFoundError:
        return JSONResponse({"error": "image not found"}, status_code=404)


@router.get("/api/datasets")
def list_datasets():
    info = {}
    for key in deps.registry.list_datasets():
        cfg = deps.registry.get(key)
        images = deps.registry.list_images(key)
        info[key] = {
            "path": str(cfg.path) if cfg else None,
            "images": len(images),
            "sample": str(images[0]) if images else None,
        }
    return JSONResponse(info)
