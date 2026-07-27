"""
Supplier Repository implementation with pgvector similarity search.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.supplier import SupplierModel
from src.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[SupplierModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(SupplierModel, session)

    async def get_by_tax_id(self, tax_id: str) -> Optional[SupplierModel]:
        stmt = select(SupplierModel).where(SupplierModel.tax_id == tax_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Optional[SupplierModel]:
        stmt = select(SupplierModel).where(SupplierModel.name.ilike(f"%{name}%"))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def find_similar_suppliers(
        self, query_vector: List[float], limit: int = 5
    ) -> List[SupplierModel]:
        """Vector similarity search using pgvector cosine distance L2/cosine operator."""
        if not query_vector:
            return []
        stmt = (
            select(SupplierModel)
            .where(SupplierModel.embedding.is_not(None))
            .order_by(SupplierModel.embedding.cosine_distance(query_vector)) # type: ignore
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
