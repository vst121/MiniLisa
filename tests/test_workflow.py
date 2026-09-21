"""
Unit and integration tests for Workflow Engine and Event Bus.
"""

import pytest

from src.config.settings import settings
from src.domain.entities import InvoiceStatus
from src.domain.events import HumanApprovedEvent, InvoiceUploadedEvent
from src.events.event_bus import InMemoryEventBus
from src.workflows.workflow_engine import WorkflowEngine
from tests.fakes import DeterministicLLMClient


@pytest.mark.asyncio
async def test_workflow_engine_auto_approval_flow():
    bus = InMemoryEventBus()
    engine = WorkflowEngine(event_bus=bus)
    engine.invoice_agent.llm_client = DeterministicLLMClient()
    await engine.register_subscribers()

    invoice_id = "inv-auto-approve-100"
    upload_event = InvoiceUploadedEvent(
        invoice_id=invoice_id,
        file_path="mock_clean_invoice.pdf",
        file_name="mock_clean_invoice.pdf",
    )

    await bus.publish(upload_event)

    checkpoint = engine.get_checkpoint(invoice_id)
    assert checkpoint is not None
    assert checkpoint.status in [InvoiceStatus.COMPLETED, InvoiceStatus.AWAITING_HUMAN_APPROVAL]


@pytest.mark.asyncio
async def test_workflow_human_approval_resume_flow():
    bus = InMemoryEventBus()
    engine = WorkflowEngine(event_bus=bus)
    await engine.register_subscribers()

    invoice_id = "inv-human-review-200"

    # Save mock checkpoint in AWAITING_HUMAN_APPROVAL state
    engine.save_checkpoint(
        invoice_id,
        "AWAITING_HUMAN_APPROVAL",
        {"invoice_extraction": {"total_amount": 1200.0, "currency": "USD"}},
        InvoiceStatus.AWAITING_HUMAN_APPROVAL,
    )

    # Trigger HumanApproved event
    human_event = HumanApprovedEvent(
        invoice_id=invoice_id,
        recommendation_id="rec-200",
        user_id="manager_user_1",
        action="APPROVE",
        comments="Approved by procurement manager",
    )

    await bus.publish(human_event)

    checkpoint = engine.get_checkpoint(invoice_id)
    assert checkpoint is not None
    assert checkpoint.status == InvoiceStatus.COMPLETED


@pytest.mark.asyncio
async def test_workflow_human_rejection_flow():
    bus = InMemoryEventBus()
    engine = WorkflowEngine(event_bus=bus)
    await engine.register_subscribers()
    invoice_id = "inv-human-reject-300"
    engine.save_checkpoint(
        invoice_id,
        "AWAITING_HUMAN_APPROVAL",
        {"invoice_extraction": {"total_amount": 100.0, "currency": "EUR"}},
        InvoiceStatus.AWAITING_HUMAN_APPROVAL,
    )

    await bus.publish(
        HumanApprovedEvent(
            invoice_id=invoice_id,
            recommendation_id="rec-300",
            user_id="manager_user_1",
            action="REJECT",
            comments="Duplicate invoice",
        )
    )

    checkpoint = engine.get_checkpoint(invoice_id)
    assert checkpoint is not None
    assert checkpoint.status == InvoiceStatus.REJECTED


def test_workflow_checkpoint_survives_engine_restart(tmp_path):
    original_checkpoint_dir = settings.WORKFLOW_CHECKPOINT_DIR
    settings.WORKFLOW_CHECKPOINT_DIR = tmp_path
    try:
        first_engine = WorkflowEngine(event_bus=InMemoryEventBus())
        first_engine.save_checkpoint(
            "inv-persisted-400",
            "AWAITING_HUMAN_APPROVAL",
            {"invoice_extraction": {"total_amount": 450.0}},
            InvoiceStatus.AWAITING_HUMAN_APPROVAL,
        )

        second_engine = WorkflowEngine(event_bus=InMemoryEventBus())
        checkpoint = second_engine.get_checkpoint("inv-persisted-400")

        assert checkpoint is not None
        assert checkpoint.status == InvoiceStatus.AWAITING_HUMAN_APPROVAL
        assert checkpoint.state_data["invoice_extraction"]["total_amount"] == 450.0
    finally:
        settings.WORKFLOW_CHECKPOINT_DIR = original_checkpoint_dir


@pytest.mark.asyncio
async def test_event_bus_retries_and_dead_letters_failed_handlers():
    bus = InMemoryEventBus()
    attempts = 0

    async def failing_handler(_event):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("handler unavailable")

    await bus.subscribe("InvoiceUploaded", failing_handler)
    await bus.publish(
        InvoiceUploadedEvent(
            invoice_id="inv-dead-letter-500",
            file_path="mock.pdf",
            file_name="mock.pdf",
        )
    )

    assert attempts == settings.EVENT_MAX_RETRIES + 1
    assert len(bus.dead_letters) == 1
