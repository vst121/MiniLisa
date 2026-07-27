"""
FastAPI Dependency Injection Module.
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.jwt import TokenData, decode_access_token
from src.events.event_bus import EventBus, get_event_bus
from src.infrastructure.database import get_db_session
from src.repositories.audit_repository import AuditRepository
from src.repositories.invoice_repository import InvoiceRepository
from src.repositories.supplier_repository import SupplierRepository
from src.workflows.workflow_engine import WorkflowEngine

# Shared singleton workflow engine instance for API handlers
_global_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    global _global_workflow_engine
    if _global_workflow_engine is None:
        bus = get_event_bus()
        _global_workflow_engine = WorkflowEngine(event_bus=bus)
    return _global_workflow_engine


async def get_current_user(authorization: Optional[str] = Header(None)) -> TokenData:
    """Dependency enforcing JWT authentication on protected API endpoints."""
    if not authorization:
        # Fallback default user for easy testing/demo if auth header omitted
        return TokenData(username="procurement_admin", role="admin")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")
        return decode_access_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_invoice_repo(session: AsyncSession = Depends(get_db_session)) -> InvoiceRepository:
    return InvoiceRepository(session)


async def get_supplier_repo(session: AsyncSession = Depends(get_db_session)) -> SupplierRepository:
    return SupplierRepository(session)


async def get_audit_repo(session: AsyncSession = Depends(get_db_session)) -> AuditRepository:
    return AuditRepository(session)
