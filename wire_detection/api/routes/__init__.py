from fastapi import APIRouter

from wire_detection.api.routes.presets import router as presets_router
from wire_detection.api.routes.datasets import router as datasets_router
from wire_detection.api.routes.process import router as process_router

api_router = APIRouter()
api_router.include_router(presets_router)
api_router.include_router(datasets_router)
api_router.include_router(process_router)
