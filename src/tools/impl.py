"""
Concrete Agent Tools Implementation.
Every tool is independent, typed with Pydantic, and unit testable.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# 1. Search Supplier Tool
# ---------------------------------------------------------
class SearchSupplierInput(BaseModel):
    supplier_name: str | None = Field(default=None, description="Name of supplier to search")
    tax_id: str | None = Field(default=None, description="Tax ID or VAT number of supplier")


class SearchSupplierTool(BaseTool):
    name = "search_supplier"
    description = (
        "Searches the enterprise database for supplier risk score, tax ID, and past history."
    )
    args_schema = SearchSupplierInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        supplier_name = kwargs.get("supplier_name", "")
        tax_id = kwargs.get("tax_id", "")
        logger.info(f"[SearchSupplierTool] Searching for name='{supplier_name}', tax_id='{tax_id}'")

        # Mock / DB lookup fallback logic
        if tax_id == "TAX-BLOCKED-99" or "RISKY" in (supplier_name or "").upper():
            return {
                "supplier_found": True,
                "supplier_id": "sup-risky-001",
                "name": supplier_name or "Risky Vendor Ltd",
                "tax_id": tax_id or "TAX-BLOCKED-99",
                "risk_score": 85.0,
                "risk_level": "HIGH",
                "status": "FLAGGED",
                "risk_factors": ["Prior fraudulent invoices", "Unverified bank account"],
            }

        return {
            "supplier_found": True,
            "supplier_id": "sup-clean-002",
            "name": supplier_name or "Acme Industrial Supplies",
            "tax_id": tax_id or "TAX-VALID-100",
            "risk_score": 5.0,
            "risk_level": "LOW",
            "status": "ACTIVE",
            "risk_factors": [],
        }


# ---------------------------------------------------------
# 2. Search Previous Purchases Tool
# ---------------------------------------------------------
class SearchPreviousPurchasesInput(BaseModel):
    supplier_name: str = Field(description="Supplier name to search historical line items for")
    item_description: str = Field(description="Description of line item to compare unit prices")


class SearchPreviousPurchasesTool(BaseTool):
    name = "search_previous_purchases"
    description = "Retrieves historical purchase order unit prices for price anomaly comparison."
    args_schema = SearchPreviousPurchasesInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        item_description = kwargs.get("item_description", "")
        logger.info(
            f"[SearchPreviousPurchasesTool] Fetching history for item: '{item_description}'"
        )

        # Returns historical baseline price
        return {
            "historical_count": 4,
            "average_unit_price": 100.0,
            "min_unit_price": 95.0,
            "max_unit_price": 105.0,
            "currency": "USD",
        }


# ---------------------------------------------------------
# 3. Calculate VAT Tool
# ---------------------------------------------------------
class CalculateVATInput(BaseModel):
    subtotal: float = Field(description="Subtotal amount before tax")
    vat_amount: float = Field(description="Claimed VAT amount on invoice")
    total_amount: float = Field(description="Claimed grand total on invoice")
    expected_vat_rate_pct: float = Field(
        default=20.0, description="Expected VAT rate percentage e.g. 20.0 for 20%"
    )


class CalculateVATTool(BaseTool):
    name = "calculate_vat"
    description = (
        "Validates mathematical consistency of subtotal + VAT = total and checks expected VAT rate."
    )
    args_schema = CalculateVATInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        subtotal = float(kwargs.get("subtotal", 0.0))
        vat_amount = float(kwargs.get("vat_amount", 0.0))
        total_amount = float(kwargs.get("total_amount", 0.0))
        expected_rate = float(kwargs.get("expected_vat_rate_pct", 20.0))

        calculated_total = round(subtotal + vat_amount, 2)
        math_correct = abs(calculated_total - total_amount) < 0.05

        expected_vat = round(subtotal * (expected_rate / 100.0), 2)
        vat_rate_correct = abs(expected_vat - vat_amount) < 1.0

        return {
            "math_correct": math_correct,
            "calculated_total": calculated_total,
            "claimed_total": total_amount,
            "expected_vat_at_rate": expected_vat,
            "claimed_vat": vat_amount,
            "vat_rate_correct": vat_rate_correct,
        }


# ---------------------------------------------------------
# 4. Currency Conversion Tool
# ---------------------------------------------------------
class CurrencyConversionInput(BaseModel):
    amount: float = Field(description="Amount in source currency")
    from_currency: str = Field(description="Source currency code (e.g. EUR, GBP)")
    to_currency: str = Field(default="USD", description="Target currency code (e.g. USD)")


class CurrencyConversionTool(BaseTool):
    name = "currency_conversion"
    description = "Converts financial amounts between different foreign currencies."
    args_schema = CurrencyConversionInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        amount = float(kwargs.get("amount", 0.0))
        from_curr = kwargs.get("from_currency", "USD").upper()
        to_curr = kwargs.get("to_currency", "USD").upper()

        rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.74}
        rate = rates.get(from_curr, 1.0) / rates.get(to_curr, 1.0)
        converted = round(amount * rate, 2)

        return {
            "original_amount": amount,
            "from_currency": from_curr,
            "to_currency": to_curr,
            "converted_amount": converted,
            "exchange_rate": rate,
        }


# ---------------------------------------------------------
# 5. ERP Connector Tool
# ---------------------------------------------------------
class ERPConnectorInput(BaseModel):
    invoice_id: str = Field(description="Invoice ID to post to ERP")
    supplier_id: str = Field(description="Supplier ID in ERP")
    amount: float = Field(description="Approved total amount")
    currency: str = Field(default="USD", description="Currency code")


class ERPConnectorTool(BaseTool):
    name = "erp_connector"
    description = (
        "Integrates with enterprise ERP system (SAP/NetSuite mock) to post approved invoices."
    )
    args_schema = ERPConnectorInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        invoice_id = kwargs.get("invoice_id")
        amount = kwargs.get("amount")
        logger.info(
            f"[ERPConnectorTool] Posting invoice {invoice_id} of amount ${amount} to fake ERP"
        )

        return {
            "success": True,
            "erp_reference_code": f"ERP-REF-{invoice_id[:8].upper()}",
            "status": "POSTED_SUCCESSFULLY",
            "message": "Invoice posted to SAP Accounts Payable queue.",
        }


# ---------------------------------------------------------
# 6. Email Sender Tool
# ---------------------------------------------------------
class EmailSenderInput(BaseModel):
    recipient_email: str = Field(description="Email address to send notification to")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email text or HTML content")


class EmailSenderTool(BaseTool):
    name = "email_sender"
    description = "Sends notification emails to procurement managers or approvers."
    args_schema = EmailSenderInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        recipient = kwargs.get("recipient_email")
        subject = kwargs.get("subject")
        logger.info(f"[EmailSenderTool] Sending email to '{recipient}' with subject '{subject}'")

        return {
            "delivered": True,
            "recipient": recipient,
            "status": "SENT",
        }


# ---------------------------------------------------------
# 7. Store Audit Tool
# ---------------------------------------------------------
class StoreAuditInput(BaseModel):
    entity_type: str = Field(description="Type of entity being audited e.g. Invoice")
    entity_id: str = Field(description="ID of entity being audited")
    event_name: str = Field(description="Audit event name")
    actor: str = Field(default="SYSTEM", description="Actor initiating event")
    details: dict[str, Any] = Field(default_factory=dict, description="Arbitrary audit log payload")


class StoreAuditTool(BaseTool):
    name = "store_audit"
    description = "Stores immutable audit log entry for system trace and compliance."
    args_schema = StoreAuditInput

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        entity_id = kwargs.get("entity_id")
        event_name = kwargs.get("event_name")
        logger.info(f"[StoreAuditTool] Audit recorded for {entity_id}: {event_name}")

        return {
            "audit_stored": True,
            "entity_id": entity_id,
            "event_name": event_name,
        }
