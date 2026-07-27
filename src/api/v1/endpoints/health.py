"""
Health Check API Endpoint.
"""

from fastapi import APIRouter
from src.config.settings import settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENV,
        "event_bus": settings.EVENT_BUS_TYPE,
    }
