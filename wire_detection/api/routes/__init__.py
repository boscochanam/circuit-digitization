from fastapi import APIRouter

from wire_detection.api.routes.presets import router as presets_router
from wire_detection.api.routes.datasets import router as datasets_router
from wire_detection.api.routes.process import router as process_router
from wire_detection.api.routes.netlist import router as netlist_router
from wire_detection.api.routes.join_overlay import router as join_overlay_router
from wire_detection.api.routes.ocr import router as ocr_router
from wire_detection.api.routes.sim_overlay import router as sim_overlay_router
from wire_detection.api.routes.current_overlay import router as current_overlay_router
from wire_detection.api.routes.topology import router as topology_router

api_router = APIRouter()
api_router.include_router(presets_router)
api_router.include_router(datasets_router)
api_router.include_router(process_router)
api_router.include_router(netlist_router)
api_router.include_router(join_overlay_router)
api_router.include_router(ocr_router)
api_router.include_router(sim_overlay_router)
api_router.include_router(current_overlay_router)
api_router.include_router(topology_router)
