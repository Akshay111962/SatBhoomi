"""API v1 router aggregate."""

from fastapi import APIRouter

from satbhoomi.api.routes.alerts import router as alerts_router
from satbhoomi.api.routes.assessments import router as assessments_router
from satbhoomi.api.routes.auth import router as auth_router
from satbhoomi.api.routes.farmer_summary import router as farmer_summary_router
from satbhoomi.api.routes.monitoring import router as monitoring_router
from satbhoomi.api.routes.plots import router as plots_router
from satbhoomi.api.routes.relief import router as relief_router
from satbhoomi.api.routes.what_if import router as what_if_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(plots_router)
api_v1_router.include_router(assessments_router)
api_v1_router.include_router(what_if_router)
api_v1_router.include_router(monitoring_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(relief_router)
api_v1_router.include_router(farmer_summary_router)

__all__ = ["api_v1_router"]
