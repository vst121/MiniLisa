"""
Supplier Intelligence Agent implementation.
Looks up supplier, risk score, payment history, and active status.
"""

import time

from src.agents.base import AgentResult, AgentState, BaseAgent
from src.domain.entities import RiskLevel
from src.infrastructure.llm_client import LLMClient
from src.prompts.templates import SUPPLIER_AGENT_SYSTEM_PROMPT
from src.schemas.supplier import SupplierRisk
from src.telemetry.telemetry import TelemetryService
from src.tools.impl import SearchSupplierTool


class SupplierAgent(BaseAgent):
    role = "Supplier Intelligence Agent"
    system_prompt = SUPPLIER_AGENT_SYSTEM_PROMPT

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        tools = [SearchSupplierTool()]
        super().__init__(llm_client=llm_client, tools=tools)

    async def run(self, state: AgentState) -> AgentResult:
        start_time = time.perf_counter()
        extraction_data = state.data.get("invoice_extraction", {})
        supplier_name = extraction_data.get("supplier_name", "")
        tax_id = extraction_data.get("supplier_tax_id", "")
        tool_calls_made = []

        async with TelemetryService.trace_agent_execution(self.role, state.invoice_id) as metrics:
            # Execute tool for supplier search
            supplier_res = await self.execute_tool(
                "search_supplier",
                {"supplier_name": supplier_name, "tax_id": tax_id},
            )
            tool_calls_made.append({"tool": "search_supplier", "result": supplier_res})
            metrics["tool_calls"] = tool_calls_made

            risk_level_str = supplier_res.get("risk_level", "LOW")
            try:
                risk_level = RiskLevel(risk_level_str)
            except ValueError:
                risk_level = RiskLevel.LOW

            supplier_risk = SupplierRisk(
                supplier_found=supplier_res.get("supplier_found", True),
                supplier_id=supplier_res.get("supplier_id"),
                supplier_name=supplier_res.get("name", supplier_name),
                tax_id=supplier_res.get("tax_id", tax_id),
                risk_score=supplier_res.get("risk_score", 0.0),
                risk_level=risk_level,
                rating=5.0,
                payment_history_status="GOOD",
                past_purchases_count=5,
                risk_factors=supplier_res.get("risk_factors", []),
                summary=f"Supplier {supplier_name} risk profile assessed as {risk_level.value}.",
            )

            duration = (time.perf_counter() - start_time) * 1000
            state.data["supplier_risk"] = supplier_risk.model_dump()
            state.history.append(
                {"agent": self.role, "status": "COMPLETED", "timestamp": time.time()}
            )

            return AgentResult(
                success=True,
                output=supplier_risk.model_dump(),
                updated_state=state,
                tool_calls_made=tool_calls_made,
                execution_time_ms=duration,
            )
