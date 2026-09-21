"""
Domain Entities and Value Objects.
Pure domain logic and core business models independent of persistence frameworks.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class InvoiceStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    CHECKING_SUPPLIER = "CHECKING_SUPPLIER"
    SUPPLIER_CHECKED = "SUPPLIER_CHECKED"
    PRICING_CHECK = "PRICING_CHECK"
    PRICING_COMPLETED = "PRICING_COMPLETED"
    RECOMMENDATION_PENDING = "RECOMMENDATION_PENDING"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RecommendationAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class InvoiceItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    invoice_id: str = ""
    description: str = ""
    quantity: float = 1.0
    unit_price: float = 0.0
    total_price: float = 0.0
    item_code: str | None = None


@dataclass
class Invoice:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_name: str = ""
    file_path: str = ""
    status: InvoiceStatus = InvoiceStatus.UPLOADED
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    total_amount: float = 0.0
    vat_amount: float = 0.0
    currency: str = "USD"
    raw_text: str = ""
    items: list[InvoiceItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def calculate_total_from_items(self) -> float:
        return sum(item.total_price for item in self.items)


@dataclass
class Supplier:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tax_id: str = ""
    email: str | None = None
    risk_score: float = 0.0  # 0.0 to 100.0 (higher means higher risk)
    risk_level: RiskLevel = RiskLevel.LOW
    rating: float = 5.0
    status: str = "ACTIVE"
    payment_terms: str = "NET_30"
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PurchaseOrder:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    po_number: str = ""
    supplier_id: str = ""
    total_amount: float = 0.0
    currency: str = "USD"
    status: str = "OPEN"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Recommendation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    invoice_id: str = ""
    action: RecommendationAction = RecommendationAction.NEEDS_HUMAN
    confidence_score: float = 0.0  # 0.0 to 1.0
    explanation: str = ""
    reasoning_summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Approval:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_id: str = ""
    invoice_id: str = ""
    user_id: str = ""
    action_taken: RecommendationAction = RecommendationAction.APPROVE
    comments: str | None = None
    approved_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AuditLog:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: str = ""
    entity_id: str = ""
    event_name: str = ""
    actor: str = "SYSTEM"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
