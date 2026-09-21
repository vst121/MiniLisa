"""
Unit tests for Database Models and Repositories using SQLite in-memory async engine.
"""

import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.database import Base
from src.models.invoice import InvoiceModel
from src.models.supplier import SupplierModel
from src.repositories.invoice_repository import InvoiceRepository
from src.repositories.supplier_repository import SupplierRepository
from src.repositories.outbox_repository import OutboxRepository
from src.events.outbox_publisher import publish_pending_events


@pytest.fixture
async def async_session():
    # SQLite async engine for fast in-memory testing
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session
        await session.rollback()

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_invoice_repository_crud(async_session: AsyncSession):
    repo = InvoiceRepository(async_session)

    invoice = InvoiceModel(
        file_name="invoice_test.pdf",
        file_path="/path/test.pdf",
        supplier_name="Acme Inc",
        total_amount=150.0,
        vat_amount=15.0,
    )
    created = await repo.create(invoice)
    assert created.id is not None
    assert created.file_name == "invoice_test.pdf"

    retrieved = await repo.get_by_id(created.id)
    assert retrieved is not None
    assert retrieved.supplier_name == "Acme Inc"


@pytest.mark.asyncio
async def test_supplier_repository_tax_lookup(async_session: AsyncSession):
    repo = SupplierRepository(async_session)
    supplier = SupplierModel(
        name="Global Tech Ltd",
        tax_id="US998877665",
        risk_score=10.0,
        risk_level="LOW",
    )
    await repo.create(supplier)

    found = await repo.get_by_tax_id("US998877665")
    assert found is not None
    assert found.name == "Global Tech Ltd"
    assert found.risk_score == 10.0


@pytest.mark.asyncio
async def test_outbox_repository_enqueue_publish_and_failure(async_session: AsyncSession):
    repo = OutboxRepository(async_session)
    event = await repo.enqueue(
        {
            "event_id": "evt-outbox-1",
            "event_type": "InvoiceUploaded",
            "correlation_id": "corr-outbox-1",
            "payload": {"invoice_id": "inv-outbox-1"},
        }
    )

    pending = await repo.get_pending()
    assert [item.event_id for item in pending] == [event.event_id]

    await repo.mark_failed(event, "temporary publish failure")
    assert event.attempts == 1
    assert event.last_error == "temporary publish failure"

    await repo.mark_published(event)
    assert await repo.get_pending() == []


@pytest.mark.asyncio
async def test_publish_pending_events_replays_event(async_session: AsyncSession):
    repo = OutboxRepository(async_session)
    await repo.enqueue(
        {
            "event_id": "evt-outbox-replay",
            "event_type": "InvoiceUploaded",
            "correlation_id": "corr-outbox-replay",
            "payload": {
                "event_id": "evt-outbox-replay",
                "event_type": "InvoiceUploaded",
                "correlation_id": "corr-outbox-replay",
                "invoice_id": "inv-replay",
                "file_path": "mock.pdf",
                "file_name": "mock.pdf",
            },
        }
    )
    await async_session.commit()

    class RecordingBus:
        def __init__(self):
            self.events = []

        async def publish(self, event):
            self.events.append(event)

    bus = RecordingBus()
    assert await publish_pending_events(async_session, bus) == 1
    assert bus.events[0].invoice_id == "inv-replay"


@pytest.mark.asyncio
async def test_outbox_worker_drains_pending_and_stops_on_signal():
    from src.outbox_worker import run_outbox_worker
    from src.events.event_bus import EventBus

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_maker() as session:
        await OutboxRepository(session).enqueue(
            {
                "event_id": "evt-worker-1",
                "event_type": "InvoiceUploaded",
                "correlation_id": "corr-worker-1",
                "payload": {
                    "event_id": "evt-worker-1",
                    "event_type": "InvoiceUploaded",
                    "correlation_id": "corr-worker-1",
                    "invoice_id": "inv-worker-1",
                    "file_path": "mock.pdf",
                    "file_name": "mock.pdf",
                },
            }
        )
        await session.commit()

    class RecordingBus(EventBus):
        def __init__(self, stop_event):
            self.events = []
            self._stop_event = stop_event

        async def publish(self, event):
            self.events.append(event)
            self._stop_event.set()

        async def subscribe(self, event_type, handler):
            pass

    stop_event = asyncio.Event()
    bus = RecordingBus(stop_event)

    await run_outbox_worker(
        session_maker=session_maker,
        event_bus=bus,
        stop_event=stop_event,
    )

    assert len(bus.events) == 1
    assert bus.events[0].invoice_id == "inv-worker-1"

    async with session_maker() as session:
        remaining = await OutboxRepository(session).get_pending()
    assert remaining == []

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_outbox_worker_is_idempotent_against_already_published_records():
    from src.outbox_worker import run_outbox_worker
    from src.events.event_bus import EventBus

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    class RecordingBus(EventBus):
        def __init__(self, stop_event):
            self.events = []
            self._stop_event = stop_event

        async def publish(self, event):
            self.events.append(event)
            self._stop_event.set()

        async def subscribe(self, event_type, handler):
            pass

    stop_event = asyncio.Event()
    bus = RecordingBus(stop_event)

    async def stop_after_delay():
        await asyncio.sleep(0.2)
        stop_event.set()

    stop_task = asyncio.create_task(stop_after_delay())
    try:
        await run_outbox_worker(
            session_maker=session_maker,
            event_bus=bus,
            stop_event=stop_event,
        )
    finally:
        stop_task.cancel()

    assert bus.events == []

    await test_engine.dispose()
