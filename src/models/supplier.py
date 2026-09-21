"""
Supplier SQLAlchemy 2 Model with pgvector embedding column.
"""

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base
from src.models.base import TimestampMixin

if TYPE_CHECKING:
    from src.models.invoice import InvoiceModel
    from src.models.purchase_order import PurchaseOrderModel


class SupplierModel(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tax_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), default="LOW", nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(100), default="NET_30", nullable=False)

    # Vector embedding column for semantic search (OpenAI 1536 dim)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    invoices: Mapped[list["InvoiceModel"]] = relationship("InvoiceModel", back_populates="supplier")
    purchase_orders: Mapped[list["PurchaseOrderModel"]] = relationship(
        "PurchaseOrderModel", back_populates="supplier"
    )
