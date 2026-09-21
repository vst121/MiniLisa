"""
Audit Log Repository implementation.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLogModel
from src.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLogModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLogModel, session)

    async def get_by_entity(self, entity_type: str, entity_id: str) -> list[AuditLogModel]:
        stmt = (
            select(AuditLogModel)
            .where(
                AuditLogModel.entity_type == entity_type,
                AuditLogModel.entity_id == entity_id,
            )
            .order_by(AuditLogModel.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
