"""
Unit tests for Infrastructure Adapters.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.domain.events import InvoiceUploadedEvent
from src.events.event_bus import InMemoryEventBus
from src.infrastructure.llm_client import LLMClient
from src.infrastructure.pdf_parser import DocumentParser
from src.schemas.validation import ValidationResult


@pytest.mark.asyncio
async def test_in_memory_event_bus() -> None:
    bus = InMemoryEventBus()
    received_events = []

    async def sample_handler(event):
        received_events.append(event)

    await bus.subscribe("InvoiceUploaded", sample_handler)

    test_event = InvoiceUploadedEvent(
        invoice_id="inv-99", file_path="/tmp/doc.pdf", file_name="doc.pdf"
    )
    await bus.publish(test_event)

    assert len(received_events) == 1
    assert received_events[0].invoice_id == "inv-99"


@pytest.mark.asyncio
async def test_llm_client_structured_output_mock() -> None:
    client = LLMClient()
    messages = [
        {"role": "system", "content": "You are a validation assistant."},
        {"role": "user", "content": "Check invoice sample"},
    ]
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"is_valid": true, "missing_fields": [], "math_correct": true, "vat_correct": true, "is_duplicate": false, "errors": [], "confidence_score": 1.0}'
                )
            )
        ]
    )

    async def mock_completion(**_kwargs):
        return response

    with patch("src.infrastructure.llm_client.acompletion", new=mock_completion):
        res = await client.generate_structured(messages, ValidationResult)
    assert isinstance(res, ValidationResult)


@pytest.mark.asyncio
async def test_llm_client_health_check_probes_chat_and_embeddings() -> None:
    client = LLMClient()

    async def mock_completion(**kwargs):
        assert kwargs["timeout"] == 60.0
        assert kwargs["num_retries"] == 3
        return SimpleNamespace()

    async def mock_embedding(**kwargs):
        assert kwargs["timeout"] == 60.0
        assert kwargs["num_retries"] == 3
        return SimpleNamespace()

    with (
        patch("src.infrastructure.llm_client.acompletion", new=mock_completion),
        patch("src.infrastructure.llm_client.aembedding", new=mock_embedding),
    ):
        result = await client.check_health()

    assert result["status"] == "healthy"
    assert result["chat"] == "healthy"
    assert result["embeddings"] == "healthy"


@pytest.mark.asyncio
async def test_llm_client_health_check_reports_degraded_provider() -> None:
    client = LLMClient()

    async def mock_completion(**_kwargs):
        return SimpleNamespace()

    async def mock_embedding(**_kwargs):
        raise RuntimeError("embedding provider unavailable")

    with (
        patch("src.infrastructure.llm_client.acompletion", new=mock_completion),
        patch("src.infrastructure.llm_client.aembedding", new=mock_embedding),
    ):
        result = await client.check_health()

    assert result["status"] == "degraded"
    assert result["chat"] == "healthy"
    assert result["embeddings"] == "unhealthy"
    assert "embedding provider unavailable" in result["embeddings_error"]


def test_document_parser_nonexistent_file() -> None:
    with pytest.raises(FileNotFoundError):
        DocumentParser.parse_pdf(Path("non_existent_file_12345.pdf"))
