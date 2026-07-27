"""
Audit Log API Endpoint.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from src.api.deps import get_audit_repo, get_current_user
from src.auth.jwt import TokenData
from src.repositories.audit_repository import AuditRepository
from src.schemas.audit import AuditLogResponse

router = APIRouter(tags=["Audit Logs"])


@router.get(
    "/audit/{id}",
    response_model=List[AuditLogResponse],
    summary="Get Audit Log History for Invoice",
    description="Retrieves the immutable audit trail of events recorded for an invoice.",
)
async def get_audit_log(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    audit_models = await audit_repo.get_by_entity("Invoice", id)
    return [
        AuditLogResponse(
            id=model.id,
            entity_type=model.entity_type,
            entity_id=model.entity_id,
            event_name=model.event_name,
            actor=model.actor,
            details=model.details,
            timestamp=model.timestamp,
        )
        for model in audit_models
    ]
