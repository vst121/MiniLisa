"""
Recommendation and Approval SQLAlchemy 2 Models.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base
from src.models.base import TimestampMixin

if TYPE_CHECKING:
    from src.models.invoice import InvoiceModel


class RecommendationModel(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    invoice: Mapped["InvoiceModel"] = relationship("InvoiceModel", back_populates="recommendation")
    approval: Mapped[Optional["ApprovalModel"]] = relationship(
        "ApprovalModel", back_populates="recommendation", uselist=False
    )


class ApprovalModel(Base, TimestampMixin):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recommendation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recommendations.id"), nullable=False, unique=True
    )
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action_taken: Mapped[str] = mapped_column(String(50), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    recommendation: Mapped["RecommendationModel"] = relationship(
        "RecommendationModel", back_populates="approval"
    )
