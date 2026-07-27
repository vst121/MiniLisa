"""
Unit tests for domain entities, events, and schemas.
"""

from src.domain.entities import Invoice, InvoiceItem, InvoiceStatus, RecommendationAction
from src.domain.events import InvoiceUploadedEvent
from src.schemas.invoice import InvoiceExtraction, InvoiceItemSchema
from src.schemas.recommendation import RecommendationResult


def test_invoice_entity_calculation() -> None:
    invoice = Invoice(
        file_name="invoice_1001.pdf",
        status=InvoiceStatus.UPLOADED,
        items=[
            InvoiceItem(description="Widget A", quantity=2, unit_price=50.0, total_price=100.0),
            InvoiceItem(description="Service B", quantity=1, unit_price=250.0, total_price=250.0),
        ],
    )
    assert invoice.calculate_total_from_items() == 350.0
    assert invoice.status == InvoiceStatus.UPLOADED


def test_invoice_extraction_schema() -> None:
    extraction = InvoiceExtraction(
        supplier_name="Acme Corp",
        total_amount=500.00,
        vat_amount=50.00,
        currency="USD",
        items=[
            InvoiceItemSchema(description="Consulting", quantity=5, unit_price=100.0, total_price=500.0)
        ],
    )
    assert extraction.supplier_name == "Acme Corp"
    assert len(extraction.items) == 1
    assert extraction.items[0].total_price == 500.0


def test_recommendation_result_schema() -> None:
    rec = RecommendationResult(
        action=RecommendationAction.NEEDS_HUMAN,
        confidence_score=0.75,
        explanation="Price variance detected on Widget line item.",
        reasoning_summary="Validation passed. Supplier risk low. Price variance +22% high.",
        flagged_issues=["PRICE_VARIANCE_HIGH"],
        requires_human_approval=True,
    )
    assert rec.action == RecommendationAction.NEEDS_HUMAN
    assert rec.requires_human_approval is True


def test_domain_event_instantiation() -> None:
    event = InvoiceUploadedEvent(
        invoice_id="inv-123",
        file_path="/storage/uploads/inv-123.pdf",
        file_name="inv-123.pdf",
    )
    assert event.event_type == "InvoiceUploaded"
    assert event.invoice_id == "inv-123"
