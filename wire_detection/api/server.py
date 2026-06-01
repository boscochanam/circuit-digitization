from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import yaml

from wire_detection.pipeline.factory import PipelineFactory
from wire_detection.pipeline.registry import STAGES
from wire_detection.data.dataset import DatasetRegistry
from wire_detection.api.cache import ImageCache
from wire_detection.api.startup import (
    load_default_config as _load_default_config_impl,
    ensure_synthetic_data,
    log_dataset_inventory,
)


# ═══════════════════════════════════════════════
# SHARED SINGLETONS (imported by route modules)
# ═══════════════════════════════════════════════

registry = DatasetRegistry()
cache = ImageCache()


def _load_default_config():
    return _load_default_config_impl()


def _ensure_synthetic_data():
    ensure_synthetic_data(registry)


def _log_dataset_inventory():
    log_dataset_inventory(registry)


# ═══════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_synthetic_data()
    _log_dataset_inventory()
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
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
