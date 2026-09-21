"""
Pricing & Anomaly Agent implementation.
Compares line item prices with historical POs/invoices and identifies price spikes.
"""

import time

from src.agents.base import AgentResult, AgentState, BaseAgent
from src.infrastructure.llm_client import LLMClient
from src.prompts.templates import PRICING_AGENT_SYSTEM_PROMPT
from src.schemas.pricing import PriceAnomaly, PricingComparison
from src.telemetry.telemetry import TelemetryService
from src.tools.impl import CurrencyConversionTool, SearchPreviousPurchasesTool


class PricingAgent(BaseAgent):
    role = "Pricing Agent"
    system_prompt = PRICING_AGENT_SYSTEM_PROMPT

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        tools = [SearchPreviousPurchasesTool(), CurrencyConversionTool()]
        super().__init__(llm_client=llm_client, tools=tools)

    async def run(self, state: AgentState) -> AgentResult:
        start_time = time.perf_counter()
        extraction_data = state.data.get("invoice_extraction", {})
        items = extraction_data.get("items", [])
        supplier_name = extraction_data.get("supplier_name", "Supplier")
        tool_calls_made = []
        anomalies: list[PriceAnomaly] = []

        async with TelemetryService.trace_agent_execution(self.role, state.invoice_id) as metrics:
            for item in items:
                desc = item.get("description", "Item")
                curr_price = float(item.get("unit_price", 0.0))

                history_res = await self.execute_tool(
                    "search_previous_purchases",
                    {"supplier_name": supplier_name, "item_description": desc},
                )
                tool_calls_made.append({"tool": "search_previous_purchases", "result": history_res})

                avg_price = float(history_res.get("average_unit_price", curr_price))
                if avg_price > 0 and curr_price > 0:
                    pct_change = ((curr_price - avg_price) / avg_price) * 100.0
                    is_anomaly = pct_change > 15.0

                    if is_anomaly:
                        anomalies.append(
                            PriceAnomaly(
                                item_description=desc,
                                current_unit_price=curr_price,
                                historical_avg_price=avg_price,
                                percentage_change=round(pct_change, 2),
                                is_anomaly=True,
                                explanation=f"Unit price ${curr_price} is {pct_change:.1f}% higher than historical avg (${avg_price}).",
                            )
                        )

            metrics["tool_calls"] = tool_calls_made
            has_anomalies = len(anomalies) > 0
            max_var = max([a.percentage_change for a in anomalies], default=0.0)

            pricing_comp = PricingComparison(
                has_pricing_anomalies=has_anomalies,
                max_price_variance_pct=max_var,
                anomalies=anomalies,
                pricing_score=100.0 - (max_var if has_anomalies else 0.0),
                summary=f"Analyzed {len(items)} items. Found {len(anomalies)} price anomalies.",
            )

            duration = (time.perf_counter() - start_time) * 1000
            state.data["pricing_comparison"] = pricing_comp.model_dump()
            state.history.append(
                {"agent": self.role, "status": "COMPLETED", "timestamp": time.time()}
            )

            return AgentResult(
                success=True,
                output=pricing_comp.model_dump(),
                updated_state=state,
                tool_calls_made=tool_calls_made,
                execution_time_ms=duration,
            )
