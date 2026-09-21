"""
Purchase Order SQLAlchemy 2 Model.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base
from src.models.base import TimestampMixin

if TYPE_CHECKING:
    from src.models.supplier import SupplierModel


class PurchaseOrderModel(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    po_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)

    # Relationship
    supplier: Mapped["SupplierModel"] = relationship(
        "SupplierModel", back_populates="purchase_orders"
    )
