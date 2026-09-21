"""
Audit Log Pydantic Schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    event_name: str
    actor: str
    details: dict[str, Any]
    timestamp: datetime
