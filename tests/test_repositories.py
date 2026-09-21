"""
Unit tests for Database Models and Repositories using SQLite in-memory async engine.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.database import Base
from src.models.invoice import InvoiceModel
from src.models.supplier import SupplierModel
from src.repositories.invoice_repository import InvoiceRepository
from src.repositories.supplier_repository import SupplierRepository
from src.repositories.outbox_repository import OutboxRepository


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
