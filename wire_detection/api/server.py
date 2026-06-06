"""Wire Detection API — FastAPI application entry point.

App setup, CORS, lifespan, and route registration only.
Actual route handlers live in api/routes/.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from wire_detection.pipeline.registry import STAGES
from wire_detection.api.deps import registry, cache, ensure_synthetic_data, log_dataset_inventory


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_synthetic_data()
    log_dataset_inventory()
    yield


app = FastAPI(title="Wire Detection Tuner", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from wire_detection.api.routes import api_router
app.include_router(api_router)


@app.get("/api/stages")
def list_stages():
    return JSONResponse(list(STAGES.keys()))


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("<html><body><h1>Wire Detection API</h1><p>Use /api/ endpoints.</p></body></html>")


def main():
    import os
    # Default to a single worker: each worker holds its OWN in-memory image +
    # pipeline cache and dataset registry, so for this (single-user, cache-sensitive,
    # CPU work already offloaded to a threadpool) tool extra workers just multiply
    # memory and quarter the cache hit-rate. Override with WIRE_TUNE_WORKERS if you
    # front it with a shared cache. uvicorn needs the import STRING (not the app
    # object) whenever workers>1, else it raises "pass the application as an import
    # string".
    workers = max(1, int(os.environ.get("WIRE_TUNE_WORKERS", "1")))
    port = int(os.environ.get("WIRE_TUNE_PORT", "8000"))
    uvicorn.run("wire_detection.api.server:app", host="0.0.0.0", port=port, workers=workers)


if __name__ == "__main__":
    main()
