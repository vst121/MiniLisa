"""
Unit tests for concrete LLM Agents.
"""

import pytest
from src.agents.base import AgentState
from src.agents.impl.invoice_agent import InvoiceAgent
from src.agents.impl.pricing_agent import PricingAgent
from src.agents.impl.recommendation_agent import RecommendationAgent
from src.agents.impl.supplier_agent import SupplierAgent
from src.agents.impl.validation_agent import ValidationAgent
from src.domain.entities import RecommendationAction
from tests.fakes import DeterministicLLMClient


@pytest.mark.asyncio
async def test_full_agent_pipeline_execution():
    state = AgentState(
        state_id="state-001",
        invoice_id="inv-test-100",
        data={
            "raw_text": "INVOICE #1001\nSupplier: Acme Industrial Supplies\nTax ID: TAX-VALID-100\nTotal: 350.00\nSubtotal: 300.00\nVAT: 50.00\nItem: Widget A Qty 2 Unit Price 150.00",
            "tables": [],
        },
    )

    # 1. Invoice Extraction Agent
    invoice_agent = InvoiceAgent(llm_client=DeterministicLLMClient())
    res1 = await invoice_agent.run(state)
    assert res1.success is True
    assert "invoice_extraction" in state.data

    # 2. Validation Agent
    val_agent = ValidationAgent()
    res2 = await val_agent.run(state)
    assert res2.success is True
    assert "validation_result" in state.data

    # 3. Supplier Agent
    sup_agent = SupplierAgent()
    res3 = await sup_agent.run(state)
    assert res3.success is True
    assert "supplier_risk" in state.data

    # 4. Pricing Agent
    price_agent = PricingAgent()
    res4 = await price_agent.run(state)
    assert res4.success is True
    assert "pricing_comparison" in state.data

    # 5. Recommendation Agent
    rec_agent = RecommendationAgent()
    res5 = await rec_agent.run(state)
    assert res5.success is True
    assert "recommendation_result" in state.data
    rec_out = res5.output
    assert rec_out["action"] in [RecommendationAction.APPROVE.value, RecommendationAction.NEEDS_HUMAN.value]
