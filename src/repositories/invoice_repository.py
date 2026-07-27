"""
Invoice Repository implementation.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities import InvoiceStatus
from src.models.invoice import InvoiceModel, InvoiceItemModel
from src.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[InvoiceModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(InvoiceModel, session)

    async def get_by_status(self, status: InvoiceStatus) -> List[InvoiceModel]:
        stmt = select(InvoiceModel).where(InvoiceModel.status == status.value)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_duplicate(self, supplier_tax_id: str, invoice_number: str) -> Optional[InvoiceModel]:
        if not supplier_tax_id or not invoice_number:
            return None
        stmt = select(InvoiceModel).where(
            InvoiceModel.supplier_tax_id == supplier_tax_id,
            InvoiceModel.invoice_number == invoice_number,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_status(self, invoice_id: str, status: InvoiceStatus) -> Optional[InvoiceModel]:
        invoice = await self.get_by_id(invoice_id)
        if invoice:
            invoice.status = status.value
            await self.session.flush()
        return invoice
