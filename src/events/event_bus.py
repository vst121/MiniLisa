"""
Event Bus Abstraction Module.
Provides an abstract EventBus, an InMemoryEventBus for tests/local dev,
and a RedisStreamsEventBus for production event-driven architecture.
"""

from abc import ABC, abstractmethod
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List
import redis.asyncio as redis
from src.config.settings import settings
from src.domain.events import BaseEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus(ABC):
    """Abstract Event Bus Port."""

    @abstractmethod
    async def publish(self, event: BaseEvent) -> None:
        """Publish a domain event to the bus."""
        pass

    @abstractmethod
    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register an async handler for a given event type."""
        pass


class InMemoryEventBus(EventBus):
    """In-Memory Event Bus for unit testing and simple single-process workflows."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = {}

    async def publish(self, event: BaseEvent) -> None:
        logger.info(f"[InMemoryEventBus] Published event: {event.event_type} (ID: {event.event_id})")
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"[InMemoryEventBus] Error in handler {handler.__name__} for event {event.event_type}: {e}")

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"[InMemoryEventBus] Subscribed handler {handler.__name__} to event: {event_type}")


class RedisStreamsEventBus(EventBus):
    """Production Redis Streams Event Bus."""

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        self._redis = redis_client or redis.from_url(settings.REDIS_URI, decode_responses=True)
        self._handlers: Dict[str, List[EventHandler]] = {}

    async def publish(self, event: BaseEvent) -> None:
        stream_key = f"events:{event.event_type}"
        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id,
            "payload": json.dumps(event.model_dump(mode="json")),
        }
        await self._redis.xadd(stream_key, event_data)
        logger.info(f"[RedisStreamsEventBus] XADD to {stream_key}: {event.event_id}")

        # Also trigger in-memory subscribers if running in same process
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            await handler(event)

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)


def get_event_bus() -> EventBus:
    """Factory function for EventBus implementation based on settings."""
    if settings.EVENT_BUS_TYPE == "redis":
        return RedisStreamsEventBus()
    return InMemoryEventBus()
