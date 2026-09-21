"""
Health Check API Endpoint.
"""

from fastapi import APIRouter

from src.config.settings import settings
from src.infrastructure.llm_client import LLMClient

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENV,
        "event_bus": settings.EVENT_BUS_TYPE,
    }


@router.get("/health/llm", summary="LLM Provider Health Check")
async def llm_health_check():
    """Probe the configured OpenRouter chat and embedding models."""
    return await LLMClient().check_health()
