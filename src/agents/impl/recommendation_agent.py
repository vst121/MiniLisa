"""
Recommendation Agent implementation.
Synthesizes validation, supplier risk, and pricing findings to produce APPROVE, REJECT, or NEEDS_HUMAN decisions.
"""

import time

from src.agents.base import AgentResult, AgentState, BaseAgent
from src.domain.entities import RecommendationAction
from src.infrastructure.llm_client import LLMClient
from src.prompts.templates import RECOMMENDATION_AGENT_SYSTEM_PROMPT
from src.schemas.recommendation import RecommendationResult
from src.telemetry.telemetry import TelemetryService


class RecommendationAgent(BaseAgent):
    role = "Recommendation Agent"
    system_prompt = RECOMMENDATION_AGENT_SYSTEM_PROMPT

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        super().__init__(llm_client=llm_client, tools=[])

    async def run(self, state: AgentState) -> AgentResult:
        start_time = time.perf_counter()
        validation = state.data.get("validation_result", {})
        supplier_risk = state.data.get("supplier_risk", {})
        pricing = state.data.get("pricing_comparison", {})

        async with TelemetryService.trace_agent_execution(self.role, state.invoice_id):
            flagged_issues = []

            # Deterministic decision synthesis rules
            if not validation.get("is_valid", True):
                flagged_issues.append("Validation failed (missing fields or math error)")

            risk_level = supplier_risk.get("risk_level", "LOW")
            if risk_level in ["HIGH", "CRITICAL"]:
                flagged_issues.append(f"Supplier risk score high ({risk_level})")

            if pricing.get("has_pricing_anomalies", False):
                flagged_issues.append(
                    f"Price anomaly detected (+{pricing.get('max_price_variance_pct', 0.0)}%)"
                )

            # Determine action
            if not validation.get("is_valid", True) or risk_level == "CRITICAL":
                action = RecommendationAction.REJECT
                confidence = 0.95
                explanation = "Invoice automatically rejected due to failed validation or critical supplier risk."
            elif len(flagged_issues) > 0:
                action = RecommendationAction.NEEDS_HUMAN
                confidence = 0.85
                explanation = f"Invoice requires human review due to flagged issues: {', '.join(flagged_issues)}."
            else:
                action = RecommendationAction.APPROVE
                confidence = 0.98
                explanation = "Invoice meets all compliance criteria, passed validation, supplier is low risk, and pricing is within baseline limits."

            requires_human = action == RecommendationAction.NEEDS_HUMAN

            rec_result = RecommendationResult(
                action=action,
                confidence_score=confidence,
                explanation=explanation,
                reasoning_summary=f"Validation: {'PASS' if validation.get('is_valid') else 'FAIL'}. Supplier Risk: {risk_level}. Pricing Anomaly: {'YES' if pricing.get('has_pricing_anomalies') else 'NO'}.",
                flagged_issues=flagged_issues,
                requires_human_approval=requires_human,
            )

            duration = (time.perf_counter() - start_time) * 1000
            state.data["recommendation_result"] = rec_result.model_dump()
            state.history.append(
                {"agent": self.role, "status": "COMPLETED", "timestamp": time.time()}
            )

            return AgentResult(
                success=True,
                output=rec_result.model_dump(),
                updated_state=state,
                execution_time_ms=duration,
            )
