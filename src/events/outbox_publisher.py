"""Publish durable outbox events and update their delivery state."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.events.event_bus import EVENT_MODELS, EventBus
from src.repositories.outbox_repository import OutboxRepository

logger = logging.getLogger(__name__)


async def publish_pending_events(
    session: AsyncSession, event_bus: EventBus, limit: int = 100
) -> int:
    """Publish pending outbox events and mark successful deliveries."""
    repository = OutboxRepository(session)
    published = 0
    for record in await repository.get_pending(limit):
        event_model = EVENT_MODELS.get(record.event_type)
        if event_model is None:
            await repository.mark_failed(record, f"Unknown event type: {record.event_type}")
            continue

        try:
            event = event_model.model_validate(record.payload)
            await event_bus.publish(event)
            await repository.mark_published(record)
            published += 1
        except Exception as exc:
            logger.exception("Outbox publication failed for %s", record.event_id)
            await repository.mark_failed(record, str(exc))
    await session.commit()
    return published
