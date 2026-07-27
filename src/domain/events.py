"""
Domain Events definition.
Used across the event bus and workflow engine.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: Dict[str, Any] = Field(default_factory=dict)


class InvoiceUploadedEvent(BaseEvent):
    event_type: str = "InvoiceUploaded"
    invoice_id: str
    file_path: str
    file_name: str


class InvoiceParsedEvent(BaseEvent):
    event_type: str = "InvoiceParsed"
    invoice_id: str
    extracted_data: Dict[str, Any]


class InvoiceValidatedEvent(BaseEvent):
    event_type: str = "InvoiceValidated"
    invoice_id: str
    is_valid: bool
    validation_issues: Dict[str, Any]


class SupplierCheckedEvent(BaseEvent):
    event_type: str = "SupplierChecked"
    invoice_id: str
    supplier_id: Optional[str]
    risk_score: float
    risk_level: str


class PricingCompletedEvent(BaseEvent):
    event_type: str = "PricingCompleted"
    invoice_id: str
    price_anomaly_detected: bool
    details: Dict[str, Any]


class RecommendationCreatedEvent(BaseEvent):
    event_type: str = "RecommendationCreated"
    invoice_id: str
    recommendation_id: str
    action: str
    confidence_score: float


class HumanApprovedEvent(BaseEvent):
    event_type: str = "HumanApproved"
    invoice_id: str
    recommendation_id: str
    user_id: str
    action: str
    comments: Optional[str] = None


class InvoiceCompletedEvent(BaseEvent):
    event_type: str = "InvoiceCompleted"
    invoice_id: str
    erp_reference: str
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
