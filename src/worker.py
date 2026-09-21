"""Redis Streams workflow worker entrypoint."""

import asyncio
import logging

from src.config.settings import settings
from src.events.event_bus import RedisStreamsEventBus
from src.workflows.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)
EVENT_TYPES = (
    "InvoiceUploaded",
    "InvoiceParsed",
    "InvoiceValidated",
    "SupplierChecked",
    "PricingCompleted",
    "RecommendationCreated",
    "HumanApproved",
)


async def run_worker() -> None:
    """Consume workflow events until the process is stopped."""
    bus = RedisStreamsEventBus()
    engine = WorkflowEngine(event_bus=bus)
    await engine.register_subscribers()
    logger.info("Workflow worker started with consumer '%s'.", settings.REDIS_CONSUMER_NAME)

    while True:
        await asyncio.gather(*(bus.consume_once(event_type) for event_type in EVENT_TYPES))


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL)
    asyncio.run(run_worker())
