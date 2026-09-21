"""Outbox publisher worker entrypoint.

Drains the durable `outbox_events` table and publishes pending records to the
configured EventBus, marking each record as published on success. This
implements the transactional outbox pattern so database writes and event
publication are never inconsistent, even when the event bus is unavailable.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import settings
from src.events.event_bus import EventBus, get_event_bus
from src.events.outbox_publisher import publish_pending_events
from src.infrastructure.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _shutdown_trigger() -> AsyncIterator[asyncio.Event]:
    """Yield until a termination signal arrives, then cancel the worker loop."""
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop(*_args):
        logger.info("Received shutdown signal; draining in-flight outbox work then stopping.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        yield stop_event
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except (KeyError, NotImplementedError, RuntimeError):
                pass


async def run_outbox_worker(
    session_maker: async_sessionmaker[AsyncSession] | None = None,
    event_bus: EventBus | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Poll the outbox and publish pending events until shutdown is requested."""
    factory = session_maker or AsyncSessionLocal
    bus = event_bus or get_event_bus()
    stop = stop_event or asyncio.Event()
    logger.info(
        "Outbox publisher started (interval=%ss, limit=%s, event_bus=%s).",
        settings.OUTBOX_PUBLISHER_INTERVAL_SECONDS,
        settings.OUTBOX_PUBLISHER_LIMIT,
        type(bus).__name__,
    )

    while not stop.is_set():
        async with factory() as session:
            try:
                published = await publish_pending_events(
                    session,
                    bus,
                    limit=settings.OUTBOX_PUBLISHER_LIMIT,
                )
                if published:
                    logger.info("Published %s outbox event(s).", published)
            except Exception:
                logger.exception("Outbox publisher iteration failed; will retry.")
                await session.rollback()
            else:
                await session.commit()

        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.OUTBOX_PUBLISHER_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass


def install_signal_handlers() -> asyncio.Event:
    """Return an asyncio.Event that is set on SIGINT/SIGTERM."""
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop(*_args):
        logger.info("Received shutdown signal; stopping outbox publisher.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            pass
    return stop_event


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL, stream=sys.stderr)
    asyncio.run(run_outbox_worker(stop_event=install_signal_handlers()))