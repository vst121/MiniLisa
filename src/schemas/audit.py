"""
Audit Log Pydantic Schemas.
"""

from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    event_name: str
    actor: str
    details: Dict[str, Any]
    timestamp: datetime
