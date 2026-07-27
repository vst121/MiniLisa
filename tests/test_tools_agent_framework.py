"""
Unit tests for Custom Agent Framework and Tools.
"""

import pytest
from src.agents.base import AgentResult, AgentState, BaseAgent, RetryPolicy
from src.schemas.validation import ValidationResult
from src.tools.impl import (
    CalculateVATTool,
    CurrencyConversionTool,
    ERPConnectorTool,
    EmailSenderTool,
    SearchPreviousPurchasesTool,
    SearchSupplierTool,
    StoreAuditTool,
)
from src.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_search_supplier_tool():
    tool = SearchSupplierTool()
    res = await tool.run(supplier_name="Acme Supplies", tax_id="TAX-123")
    assert res["supplier_found"] is True
    assert res["tax_id"] == "TAX-123"


@pytest.mark.asyncio
async def test_calculate_vat_tool():
    tool = CalculateVATTool()
    res = await tool.run(subtotal=100.0, vat_amount=20.0, total_amount=120.0, expected_vat_rate_pct=20.0)
    assert res["math_correct"] is True
    assert res["vat_rate_correct"] is True


@pytest.mark.asyncio
async def test_currency_conversion_tool():
    tool = CurrencyConversionTool()
    res = await tool.run(amount=100.0, from_currency="EUR", to_currency="USD")
    assert res["converted_amount"] == 108.0


@pytest.mark.asyncio
async def test_erp_connector_tool():
    tool = ERPConnectorTool()
    res = await tool.run(invoice_id="inv-100", supplier_id="sup-1", amount=500.0)
    assert res["success"] is True
    assert "ERP-REF-" in res["erp_reference_code"]


@pytest.mark.asyncio
async def test_email_sender_tool():
    tool = EmailSenderTool()
    res = await tool.run(recipient_email="approver@company.com", subject="Invoice Review", body="Please approve")
    assert res["delivered"] is True


@pytest.mark.asyncio
async def test_store_audit_tool():
    tool = StoreAuditTool()
    res = await tool.run(entity_type="Invoice", entity_id="inv-100", event_name="Approved")
    assert res["audit_stored"] is True


def test_tool_registry():
    registry = ToolRegistry([CalculateVATTool(), SearchSupplierTool()])
    assert len(registry.get_all_tools()) == 2
    assert registry.get_tool("calculate_vat") is not None
    schemas = registry.get_json_schemas()
    assert len(schemas) == 2
    assert schemas[0]["name"] in ["calculate_vat", "search_supplier"]
