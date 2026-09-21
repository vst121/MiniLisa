"""
Event-Driven Workflow Engine with Checkpointing and Human-in-the-Loop support.
Executes document processing, agent pipeline, state checkpointing, pause/resume, and ERP posting.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.agents.base import AgentState
from src.agents.impl import (
    InvoiceAgent,
    PricingAgent,
    RecommendationAgent,
    SupplierAgent,
    ValidationAgent,
)
from src.config.settings import settings
from src.domain.entities import InvoiceStatus, RecommendationAction
from src.domain.events import (
    BaseEvent,
    InvoiceCompletedEvent,
    InvoiceParsedEvent,
    InvoiceValidatedEvent,
    PricingCompletedEvent,
    RecommendationCreatedEvent,
    SupplierCheckedEvent,
)
from src.events.event_bus import EventBus, get_event_bus
from src.infrastructure.pdf_parser import DocumentParser
from src.tools.impl import ERPConnectorTool, StoreAuditTool

logger = logging.getLogger(__name__)


@dataclass
class WorkflowCheckpoint:
    """Persistent workflow checkpoint snapshot for resume capability."""

    invoice_id: str
    current_step: str
    state_data: dict[str, Any]
    status: InvoiceStatus
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WorkflowEngine:
    """Custom Event-Driven Workflow Engine supporting retries, checkpointing, and human approval."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or get_event_bus()
        self.checkpoints: dict[str, WorkflowCheckpoint] = {}
        self.checkpoint_path = settings.WORKFLOW_CHECKPOINT_DIR / "workflow_checkpoints.sqlite3"
        self._initialize_checkpoint_store()
        self._load_checkpoints()

        # Instantiate agents
        self.invoice_agent = InvoiceAgent()
        self.validation_agent = ValidationAgent()
        self.supplier_agent = SupplierAgent()
        self.pricing_agent = PricingAgent()
        self.recommendation_agent = RecommendationAgent()

        # Instantiate tools
        self.erp_tool = ERPConnectorTool()
        self.audit_tool = StoreAuditTool()

    def _initialize_checkpoint_store(self) -> None:
        """Create the durable checkpoint table when the workflow engine starts."""
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.checkpoint_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                    invoice_id TEXT PRIMARY KEY,
                    current_step TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _load_checkpoints(self) -> None:
        """Restore checkpoints from SQLite so process memory is not the source of truth."""
        try:
            with sqlite3.connect(self.checkpoint_path) as connection:
                rows = connection.execute(
                    "SELECT invoice_id, current_step, state_data, status, updated_at "
                    "FROM workflow_checkpoints"
                ).fetchall()
            self.checkpoints = {
                invoice_id: WorkflowCheckpoint(
                    invoice_id=invoice_id,
                    current_step=current_step,
                    state_data=json.loads(state_data),
                    status=InvoiceStatus(status),
                    updated_at=datetime.fromisoformat(updated_at),
                )
                for invoice_id, current_step, state_data, status, updated_at in rows
            }
        except (json.JSONDecodeError, TypeError, ValueError, sqlite3.Error) as exc:
            logger.warning(
                "Checkpoint store was unreadable; starting with empty checkpoint set: %s", exc
            )
            self.checkpoints = {}

    def save_checkpoint(
        self, invoice_id: str, step: str, state_data: dict[str, Any], status: InvoiceStatus
    ) -> None:
        """Save a checkpoint in memory and persist it transactionally to SQLite."""
        logger.info(
            f"💾 [CHECKPOINT] Invoice '{invoice_id}' at step '{step}' with status '{status.value}'"
        )
        checkpoint = WorkflowCheckpoint(
            invoice_id=invoice_id,
            current_step=step,
            state_data=state_data,
            status=status,
        )
        self.checkpoints[invoice_id] = checkpoint
        with sqlite3.connect(self.checkpoint_path) as connection:
            connection.execute(
                """
                INSERT INTO workflow_checkpoints
                    (invoice_id, current_step, state_data, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(invoice_id) DO UPDATE SET
                    current_step = excluded.current_step,
                    state_data = excluded.state_data,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    checkpoint.invoice_id,
                    checkpoint.current_step,
                    json.dumps(checkpoint.state_data, default=str),
                    checkpoint.status.value,
                    checkpoint.updated_at.isoformat(),
                ),
            )

    def get_checkpoint(self, invoice_id: str) -> WorkflowCheckpoint | None:
        """Retrieve stored checkpoint snapshot."""
        return self.checkpoints.get(invoice_id)

    async def register_subscribers(self) -> None:
        """Subscribe event handlers to the domain event bus."""
        await self.event_bus.subscribe("InvoiceUploaded", self.handle_invoice_uploaded)
        await self.event_bus.subscribe("InvoiceParsed", self.handle_invoice_parsed)
        await self.event_bus.subscribe("InvoiceValidated", self.handle_invoice_validated)
        await self.event_bus.subscribe("SupplierChecked", self.handle_supplier_checked)
        await self.event_bus.subscribe("PricingCompleted", self.handle_pricing_completed)
        await self.event_bus.subscribe("RecommendationCreated", self.handle_recommendation_created)
        await self.event_bus.subscribe("HumanApproved", self.handle_human_approved)

    # ---------------------------------------------------------
    # Event Handlers
    # ---------------------------------------------------------

    async def handle_invoice_uploaded(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        file_path = event.payload.get("file_path") or getattr(event, "file_path", "")
        logger.info(f"▶️ [WORKFLOW STEP 1] Processing uploaded invoice: {invoice_id}")

        try:
            # Parse document text/tables if path exists
            if file_path and not file_path.startswith("mock"):
                extracted_doc = DocumentParser.parse_pdf(file_path)
                raw_text = extracted_doc.raw_text
                tables = extracted_doc.tables
            else:
                raw_text = f"INVOICE #{invoice_id[:8]}\nSupplier: Acme Industrial Supplies\nTax ID: TAX-VALID-100\nTotal: 350.00\nSubtotal: 300.00\nVAT: 50.00"
                tables = []

            state = AgentState(
                state_id=f"st-{invoice_id}",
                invoice_id=invoice_id,
                data={"raw_text": raw_text, "tables": tables},
            )

            # Run Invoice Extraction Agent
            agent_res = await self.invoice_agent.run(state)
            if not agent_res.success:
                raise RuntimeError(f"Invoice Extraction Agent failed: {agent_res.error}")

            self.save_checkpoint(invoice_id, "PARSED", state.data, InvoiceStatus.PARSED)

            # Publish InvoiceParsed Event
            await self.event_bus.publish(
                InvoiceParsedEvent(
                    invoice_id=invoice_id,
                    extracted_data=state.data.get("invoice_extraction", {}),
                    correlation_id=event.correlation_id,
                )
            )
        except Exception as e:
            logger.error(f"❌ Workflow error handling InvoiceUploaded for {invoice_id}: {e}")
            self.save_checkpoint(invoice_id, "FAILED", {"error": str(e)}, InvoiceStatus.FAILED)

    async def handle_invoice_parsed(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        checkpoint = self.get_checkpoint(invoice_id)
        if not checkpoint:
            return

        logger.info(f"▶️ [WORKFLOW STEP 2] Validating invoice: {invoice_id}")
        state = AgentState(
            state_id=f"st-{invoice_id}", invoice_id=invoice_id, data=checkpoint.state_data
        )

        agent_res = await self.validation_agent.run(state)
        val_output = agent_res.output or {}
        self.save_checkpoint(invoice_id, "VALIDATED", state.data, InvoiceStatus.VALIDATED)

        await self.event_bus.publish(
            InvoiceValidatedEvent(
                invoice_id=invoice_id,
                is_valid=val_output.get("is_valid", True),
                validation_issues=val_output,
                correlation_id=event.correlation_id,
            )
        )

    async def handle_invoice_validated(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        checkpoint = self.get_checkpoint(invoice_id)
        if not checkpoint:
            return

        logger.info(f"▶️ [WORKFLOW STEP 3] Checking supplier risk: {invoice_id}")
        state = AgentState(
            state_id=f"st-{invoice_id}", invoice_id=invoice_id, data=checkpoint.state_data
        )

        agent_res = await self.supplier_agent.run(state)
        sup_output = agent_res.output or {}
        self.save_checkpoint(
            invoice_id, "SUPPLIER_CHECKED", state.data, InvoiceStatus.SUPPLIER_CHECKED
        )

        await self.event_bus.publish(
            SupplierCheckedEvent(
                invoice_id=invoice_id,
                supplier_id=sup_output.get("supplier_id"),
                risk_score=sup_output.get("risk_score", 0.0),
                risk_level=sup_output.get("risk_level", "LOW"),
                correlation_id=event.correlation_id,
            )
        )

    async def handle_supplier_checked(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        checkpoint = self.get_checkpoint(invoice_id)
        if not checkpoint:
            return

        logger.info(f"▶️ [WORKFLOW STEP 4] Checking pricing anomalies: {invoice_id}")
        state = AgentState(
            state_id=f"st-{invoice_id}", invoice_id=invoice_id, data=checkpoint.state_data
        )

        agent_res = await self.pricing_agent.run(state)
        price_output = agent_res.output or {}
        self.save_checkpoint(
            invoice_id, "PRICING_COMPLETED", state.data, InvoiceStatus.PRICING_COMPLETED
        )

        await self.event_bus.publish(
            PricingCompletedEvent(
                invoice_id=invoice_id,
                price_anomaly_detected=price_output.get("has_pricing_anomalies", False),
                details=price_output,
                correlation_id=event.correlation_id,
            )
        )

    async def handle_pricing_completed(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        checkpoint = self.get_checkpoint(invoice_id)
        if not checkpoint:
            return

        logger.info(f"▶️ [WORKFLOW STEP 5] Generating recommendation: {invoice_id}")
        state = AgentState(
            state_id=f"st-{invoice_id}", invoice_id=invoice_id, data=checkpoint.state_data
        )

        agent_res = await self.recommendation_agent.run(state)
        rec_output = agent_res.output or {}
        self.save_checkpoint(
            invoice_id, "RECOMMENDATION_CREATED", state.data, InvoiceStatus.RECOMMENDATION_PENDING
        )

        await self.event_bus.publish(
            RecommendationCreatedEvent(
                invoice_id=invoice_id,
                recommendation_id=f"rec-{invoice_id}",
                action=rec_output.get("action", "NEEDS_HUMAN"),
                confidence_score=rec_output.get("confidence_score", 0.8),
                correlation_id=event.correlation_id,
            )
        )

    async def handle_recommendation_created(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        checkpoint = self.get_checkpoint(invoice_id)
        if not checkpoint:
            return

        rec_result = checkpoint.state_data.get("recommendation_result", {})
        action = rec_result.get("action", RecommendationAction.NEEDS_HUMAN.value)

        if action == RecommendationAction.NEEDS_HUMAN.value:
            logger.info(f"⏸ [WORKFLOW PAUSED] Invoice '{invoice_id}' requires Human Approval.")
            self.save_checkpoint(
                invoice_id,
                "AWAITING_HUMAN_APPROVAL",
                checkpoint.state_data,
                InvoiceStatus.AWAITING_HUMAN_APPROVAL,
            )
        elif action == RecommendationAction.APPROVE.value:
            logger.info(f"⚡ [AUTO-APPROVE] Invoice '{invoice_id}' approved. Executing ERP sync.")
            await self._finalize_and_post_erp(
                invoice_id, checkpoint.state_data, event.correlation_id
            )
        elif action == RecommendationAction.REJECT.value:
            logger.info(f"⛔ [AUTO-REJECT] Invoice '{invoice_id}' rejected.")
            self.save_checkpoint(
                invoice_id, "REJECTED", checkpoint.state_data, InvoiceStatus.REJECTED
            )
            await self.audit_tool.run(
                entity_type="Invoice",
                entity_id=invoice_id,
                event_name="InvoiceRejected",
                actor="SYSTEM_RECOMMENDATION_AGENT",
                details=rec_result,
            )

    async def handle_human_approved(self, event: BaseEvent) -> None:
        invoice_id = event.payload.get("invoice_id") or getattr(event, "invoice_id", "")
        action_taken = event.payload.get("action") or getattr(event, "action", "APPROVE")
        user_id = event.payload.get("user_id") or getattr(event, "user_id", "human_user")

        logger.info(
            f"▶️ [WORKFLOW RESUMED] Received Human Approval ({action_taken}) for invoice: {invoice_id}"
        )
        checkpoint = self.get_checkpoint(invoice_id)
        state_data = checkpoint.state_data if checkpoint else {}

        await self.audit_tool.run(
            entity_type="Invoice",
            entity_id=invoice_id,
            event_name=f"HumanDecision:{action_taken}",
            actor=user_id,
            details=state_data,
        )

        if action_taken == RecommendationAction.APPROVE.value:
            await self._finalize_and_post_erp(invoice_id, state_data, event.correlation_id)
        else:
            self.save_checkpoint(invoice_id, "REJECTED", state_data, InvoiceStatus.REJECTED)

    async def _finalize_and_post_erp(
        self, invoice_id: str, state_data: dict[str, Any], correlation_id: str
    ) -> None:
        """Post to ERP system and seal audit trail."""
        extraction = state_data.get("invoice_extraction", {})
        total_amt = extraction.get("total_amount", 350.0)

        erp_res = await self.erp_tool.run(
            invoice_id=invoice_id,
            supplier_id=state_data.get("supplier_risk", {}).get("supplier_id", "sup-001"),
            amount=total_amt,
            currency=extraction.get("currency", "USD"),
        )

        self.save_checkpoint(invoice_id, "COMPLETED", state_data, InvoiceStatus.COMPLETED)

        # Publish final InvoiceCompleted event
        await self.event_bus.publish(
            InvoiceCompletedEvent(
                invoice_id=invoice_id,
                erp_reference=erp_res.get("erp_reference_code", f"ERP-{invoice_id[:8]}"),
                correlation_id=correlation_id,
            )
        )
        logger.info(
            f"🎉 [WORKFLOW COMPLETED] Invoice '{invoice_id}' posted to ERP ({erp_res.get('erp_reference_code')})"
        )
