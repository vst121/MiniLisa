"""
Custom Agent Framework Core.
Lightweight, typed, resilient, and observable agent framework interface.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from src.infrastructure.llm_client import LLMClient
from src.telemetry.telemetry import TelemetryService
from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentState(BaseModel):
    """Shared typed state passed between agents and workflow steps."""

    state_id: str
    invoice_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Standardized output produced by an Agent run."""

    success: bool
    output: dict[str, Any] | None = None
    updated_state: AgentState
    tool_calls_made: list[dict[str, Any]] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0}
    )
    error: str | None = None


class RetryPolicy(BaseModel):
    """Resilience policy for agent LLM execution retries."""

    max_retries: int = 3
    backoff_factor: float = 1.5
    retry_on_exceptions: list[str] = Field(default_factory=lambda: ["Exception"])


class BaseAgent(ABC):
    """Abstract Base Agent implementing the custom lightweight agent framework."""

    role: str
    system_prompt: str
    tools: list[BaseTool]
    retry_policy: RetryPolicy = RetryPolicy()

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        tools: list[BaseTool] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.tool_registry = ToolRegistry(tools or getattr(self, "tools", []))
        if retry_policy:
            self.retry_policy = retry_policy

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Helper to invoke a registered tool safely with telemetry logging."""
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' is not registered on agent '{self.role}'")

        start = time.perf_counter()
        try:
            result = await tool.run(**arguments)
            duration = (time.perf_counter() - start) * 1000
            TelemetryService.log_tool_call(self.role, tool_name, arguments, result, duration)
            return result
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(f"[Agent Tool Error] {self.role} -> {tool_name} failed: {e}")
            raise

    async def invoke_llm_with_retry(
        self,
        messages: list[dict[str, str]],
        response_schema: type[T],
    ) -> T:
        """Execute LLM call with configurable exponential backoff retry policy."""
        attempt = 0
        last_exception = None

        while attempt <= self.retry_policy.max_retries:
            try:
                return await self.llm_client.generate_structured(messages, response_schema)
            except Exception as e:
                attempt += 1
                last_exception = e
                if attempt > self.retry_policy.max_retries:
                    break
                sleep_time = self.retry_policy.backoff_factor**attempt
                logger.warning(
                    f"[{self.role}] LLM call failed (Attempt {attempt}/{self.retry_policy.max_retries}). Retrying in {sleep_time:.1f}s... Error: {e}"
                )
                await asyncio.sleep(sleep_time)

        raise RuntimeError(
            f"[{self.role}] LLM execution failed after {self.retry_policy.max_retries} retries: {last_exception}"
        )

    @abstractmethod
    async def run(self, state: AgentState) -> AgentResult:
        """Main agent entrypoint. Must be implemented by concrete agent subclasses."""
        pass
