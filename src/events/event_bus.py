"""
Event Bus Abstraction Module.
Provides an abstract EventBus, an InMemoryEventBus for tests/local dev,
and a RedisStreamsEventBus for production event-driven architecture.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any

import redis.asyncio as redis

from src.config.settings import settings
from src.domain.events import (
    BaseEvent,
    HumanApprovedEvent,
    InvoiceCompletedEvent,
    InvoiceParsedEvent,
    InvoiceUploadedEvent,
    InvoiceValidatedEvent,
    PricingCompletedEvent,
    RecommendationCreatedEvent,
    SupplierCheckedEvent,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]
EVENT_MODELS = {
    event_type: event_model
    for event_type, event_model in (
        ("InvoiceUploaded", InvoiceUploadedEvent),
        ("InvoiceParsed", InvoiceParsedEvent),
        ("InvoiceValidated", InvoiceValidatedEvent),
        ("SupplierChecked", SupplierCheckedEvent),
        ("PricingCompleted", PricingCompletedEvent),
        ("RecommendationCreated", RecommendationCreatedEvent),
        ("HumanApproved", HumanApprovedEvent),
        ("InvoiceCompleted", InvoiceCompletedEvent),
    )
}


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
        self._handlers: dict[str, list[EventHandler]] = {}
        self.dead_letters: list[BaseEvent] = []

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
        logger.info(
            f"[InMemoryEventBus] Subscribed handler {handler.__name__} to event: {event_type}"
        )


class RedisStreamsEventBus(EventBus):
    """Production Redis Streams Event Bus."""

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client or redis.from_url(settings.REDIS_URI, decode_responses=True)
        self._handlers: dict[str, list[EventHandler]] = {}

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

        if settings.EVENT_LOCAL_DISPATCH:
            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                error = await _dispatch_with_retries(handler, event)
                if error:
                    await self._redis.xadd(
                        f"dead-letter:{event.event_type}",
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

    async def consume_once(self, event_type: str) -> int:
        """Process one Redis consumer-group batch for an event type."""
        stream_key = f"events:{event_type}"
        try:
            await self._redis.xgroup_create(
                stream_key,
                settings.REDIS_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        batches = await self._redis.xreadgroup(
            settings.REDIS_CONSUMER_GROUP,
            settings.REDIS_CONSUMER_NAME,
            streams={stream_key: ">"},
            count=10,
            block=settings.REDIS_STREAM_BLOCK_MS,
        )
        processed = 0
        event_model = EVENT_MODELS[event_type]
        for _, entries in batches or []:
            for message_id, values in entries:
                event = event_model.model_validate(json.loads(values["payload"]))
                error = None
                for handler in self._handlers.get(event_type, []):
                    error = await _dispatch_with_retries(handler, event)
                    if error:
                        await self._redis.xadd(
                            f"dead-letter:{event_type}",
                            {
                                **values,
                                "error": str(error),
                                "dead_letter_reason": "handler_retries_exhausted",
                            },
                        )
                        break
                await self._redis.xack(stream_key, settings.REDIS_CONSUMER_GROUP, message_id)
                processed += 1
        return processed


def get_event_bus() -> EventBus:
    """Factory function for EventBus implementation based on settings."""
    if settings.EVENT_BUS_TYPE == "redis":
        return RedisStreamsEventBus()
    return InMemoryEventBus()
