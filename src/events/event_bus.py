"""
Event Bus Abstraction Module.
Provides an abstract EventBus, an InMemoryEventBus for tests/local dev,
and a RedisStreamsEventBus for production event-driven architecture.
"""

from abc import ABC, abstractmethod
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

import redis.asyncio as redis

from src.config.settings import settings
from src.domain.events import BaseEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


async def _dispatch_with_retries(handler: EventHandler, event: BaseEvent) -> Exception | None:
    """Run a handler with a bounded retry budget and return the final error."""
    last_error: Exception | None = None
    for attempt in range(settings.EVENT_MAX_RETRIES + 1):
        try:
            await handler(event)
            return None
        except Exception as exc:
            last_error = exc
            if attempt < settings.EVENT_MAX_RETRIES:
                logger.warning(
                    "Event handler retry %s/%s for %s (correlation_id=%s): %s",
                    attempt + 1,
                    settings.EVENT_MAX_RETRIES,
                    event.event_type,
                    event.correlation_id,
                    exc,
                )
                await asyncio.sleep(settings.EVENT_RETRY_DELAY_SECONDS)
    return last_error


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
        self.dead_letters: List[BaseEvent] = []

    async def publish(self, event: BaseEvent) -> None:
        logger.info(
            "[InMemoryEventBus] Published event: %s (ID: %s, correlation_id=%s)",
            event.event_type,
            event.event_id,
            event.correlation_id,
        )
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            error = await _dispatch_with_retries(handler, event)
            if error:
                self.dead_letters.append(event)
                logger.error(
                    "[InMemoryEventBus] Dead-lettered %s (correlation_id=%s): %s",
                    event.event_type,
                    event.correlation_id,
                    error,
                )

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
        logger.info(
            "[RedisStreamsEventBus] XADD to %s: %s (correlation_id=%s)",
            stream_key,
            event.event_id,
            event.correlation_id,
        )

        # Also trigger in-memory subscribers if running in same process
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            error = await _dispatch_with_retries(handler, event)
            if error:
                dead_letter_key = f"dead-letter:{event.event_type}"
                await self._redis.xadd(
                    dead_letter_key,
                    {
                        **event_data,
                        "error": str(error),
                        "dead_letter_reason": "handler_retries_exhausted",
                    },
                )
                logger.error(
                    "[RedisStreamsEventBus] Dead-lettered %s (correlation_id=%s): %s",
                    event.event_type,
                    event.correlation_id,
                    error,
                )

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)


def get_event_bus() -> EventBus:
    """Factory function for EventBus implementation based on settings."""
    if settings.EVENT_BUS_TYPE == "redis":
        return RedisStreamsEventBus()
    return InMemoryEventBus()
