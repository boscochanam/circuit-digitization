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
    # uvicorn requires an import string (not the app object) when workers>1/reload,
    # otherwise `wire-tune` crashes with "You must pass the application as an import
    # string to enable 'reload' or 'workers'." Pass the import path so multi-worker
    # launch works.
    uvicorn.run("wire_detection.api.server:app", host="0.0.0.0", port=8000, workers=4)


if __name__ == "__main__":
    main()
