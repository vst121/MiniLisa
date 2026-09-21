"""Repository for durable domain event outbox records."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outbox import OutboxEventModel


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(self, event_data: dict) -> OutboxEventModel:
        event = OutboxEventModel(**event_data)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_pending(self, limit: int = 100) -> list[OutboxEventModel]:
        result = await self.session.execute(
            select(OutboxEventModel)
            .where(OutboxEventModel.published_at.is_(None))
            .order_by(OutboxEventModel.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_event_id(self, event_id: str) -> OutboxEventModel | None:
        result = await self.session.execute(
            select(OutboxEventModel).where(OutboxEventModel.event_id == event_id)
        )
        return result.scalar_one_or_none()

    async def mark_published(self, event: OutboxEventModel) -> None:
        event.published_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def mark_failed(self, event: OutboxEventModel, error: str) -> None:
        event.attempts += 1
        event.last_error = error
        await self.session.flush()
