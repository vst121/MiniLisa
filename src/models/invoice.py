"""
Invoice and InvoiceItem SQLAlchemy 2 ORM Models.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities import InvoiceStatus
from src.infrastructure.database import Base
from src.models.base import TimestampMixin

if TYPE_CHECKING:
    from src.models.recommendation import RecommendationModel
    from src.models.supplier import SupplierModel


class InvoiceModel(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=InvoiceStatus.UPLOADED.value, nullable=False, index=True
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    invoice_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=True
    )
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_tax_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vat_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Relationships
    items: Mapped[list["InvoiceItemModel"]] = relationship(
        "InvoiceItemModel", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )
    supplier: Mapped[Optional["SupplierModel"]] = relationship(
        "SupplierModel", back_populates="invoices"
    )
    recommendation: Mapped[Optional["RecommendationModel"]] = relationship(
        "RecommendationModel", back_populates="invoice", uselist=False
    )


class InvoiceItemModel(Base):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationship
    invoice: Mapped["InvoiceModel"] = relationship("InvoiceModel", back_populates="items")
