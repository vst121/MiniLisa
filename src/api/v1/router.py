"""
API v1 Main Router Aggregator.
"""

from fastapi import APIRouter
from src.api.v1.endpoints import audit, health, invoices, recommendations

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(invoices.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(audit.router)
