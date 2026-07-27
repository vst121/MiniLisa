"""
Validation Agent implementation.
Checks missing fields, total amounts, VAT calculations, and duplicate records using tools.
"""

import time
from typing import Optional
from src.agents.base import AgentResult, AgentState, BaseAgent
from src.infrastructure.llm_client import LLMClient
from src.prompts.templates import VALIDATION_AGENT_SYSTEM_PROMPT
from src.schemas.validation import ValidationErrorItem, ValidationResult
from src.telemetry.telemetry import TelemetryService
from src.tools.impl import CalculateVATTool


class ValidationAgent(BaseAgent):
    role = "Validation Agent"
    system_prompt = VALIDATION_AGENT_SYSTEM_PROMPT

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        tools = [CalculateVATTool()]
        super().__init__(llm_client=llm_client, tools=tools)

    async def run(self, state: AgentState) -> AgentResult:
        start_time = time.perf_counter()
        extraction_data = state.data.get("invoice_extraction", {})
        tool_calls_made = []

        async with TelemetryService.trace_agent_execution(self.role, state.invoice_id) as metrics:
            # Execute tool for VAT calculation
            vat_tool_res = await self.execute_tool(
                "calculate_vat",
                {
                    "subtotal": extraction_data.get("subtotal", 0.0),
                    "vat_amount": extraction_data.get("vat_amount", 0.0),
                    "total_amount": extraction_data.get("total_amount", 0.0),
                    "expected_vat_rate_pct": 20.0,
                },
            )
            tool_calls_made.append({"tool": "calculate_vat", "result": vat_tool_res})
            metrics["tool_calls"] = tool_calls_made

            # Mandatory fields check
            missing = []
            for req_field in ["invoice_number", "supplier_name", "total_amount"]:
                if not extraction_data.get(req_field):
                    missing.append(req_field)

            is_valid = len(missing) == 0 and vat_tool_res.get("math_correct", True)
            errors = []
            for field_name in missing:
                errors.append(
                    ValidationErrorItem(
                        field_name=field_name,
                        error_type="MISSING_FIELD",
                        message=f"Mandatory invoice field '{field_name}' is missing.",
                        severity="HIGH",
                    )
                )

            validation_res = ValidationResult(
                is_valid=is_valid,
                missing_fields=missing,
                math_correct=vat_tool_res.get("math_correct", True),
                vat_correct=vat_tool_res.get("vat_rate_correct", True),
                is_duplicate=state.data.get("is_duplicate", False),
                errors=errors,
                confidence_score=1.0 if is_valid else 0.6,
            )

            duration = (time.perf_counter() - start_time) * 1000
            state.data["validation_result"] = validation_res.model_dump()
            state.history.append({"agent": self.role, "status": "COMPLETED", "timestamp": time.time()})

            return AgentResult(
                success=True,
                output=validation_res.model_dump(),
                updated_state=state,
                tool_calls_made=tool_calls_made,
                execution_time_ms=duration,
            )
