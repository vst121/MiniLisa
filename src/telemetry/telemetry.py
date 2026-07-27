"""
Telemetry & Observability Module.
Provides OpenTelemetry tracing spans and Langfuse execution metrics logging.
"""

from contextlib import asynccontextmanager
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from src.config.settings import settings

logger = logging.getLogger("telemetry")
tracer = trace.get_tracer("procurement_ai_tracer")


class TelemetryService:
    """Central Telemetry & Observability tracker."""

    @staticmethod
    @asynccontextmanager
    async def trace_agent_execution(
        agent_name: str, invoice_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Async context manager tracing agent execution, latency, and tokens."""
        start_time = time.perf_counter()
        metrics: Dict[str, Any] = {"token_usage": {"prompt": 0, "completion": 0, "total": 0}, "tool_calls": []}
        
        with tracer.start_as_current_span(f"AgentExecution:{agent_name}") as span:
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("invoice.id", invoice_id)
            if metadata:
                for k, v in metadata.items():
                    span.set_attribute(f"agent.metadata.{k}", str(v))
            
            logger.info(f"⚡ [AGENT START] {agent_name} for invoice: {invoice_id}")
            try:
                yield metrics
                duration = (time.perf_counter() - start_time) * 1000
                span.set_attribute("agent.duration_ms", duration)
                span.set_status(Status(StatusCode.OK))
                logger.info(f"✅ [AGENT COMPLETE] {agent_name} in {duration:.2f}ms | Tools: {len(metrics['tool_calls'])}")
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                span.set_attribute("agent.duration_ms", duration)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.error(f"❌ [AGENT FAILED] {agent_name} after {duration:.2f}ms: {e}")
                raise

    @staticmethod
    def log_tool_call(agent_name: str, tool_name: str, inputs: Dict[str, Any], result: Any, execution_time_ms: float) -> None:
        """Log tool invocation telemetry."""
        logger.info(f"🛠 [TOOL CALL] {agent_name} -> {tool_name} ({execution_time_ms:.2f}ms) | Args: {inputs}")
        with tracer.start_as_current_span(f"ToolCall:{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("tool.execution_time_ms", execution_time_ms)
