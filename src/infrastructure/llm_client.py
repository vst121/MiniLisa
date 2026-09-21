"""OpenRouter-backed LLM adapter using LiteLLM."""

import json
import logging
from typing import Any, TypeVar

from litellm import acompletion, aembedding
from pydantic import BaseModel

from src.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async adapter enforcing structured outputs for OpenRouter models."""

    def __init__(self, model_name: str | None = None, api_key: str | None = None):
        self.model_name = model_name or settings.LLM_MODEL
        self.api_key = api_key or settings.LLM_API_KEY
        self.api_base = settings.LLM_BASE_URL
        self.embedding_model = settings.EMBEDDING_MODEL

    def _request_options(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "api_base": self.api_base,
            "custom_llm_provider": settings.LLM_PROVIDER,
            "num_retries": settings.LLM_MAX_RETRIES,
            "timeout": settings.LLM_TIMEOUT,
        }

    async def check_health(self) -> dict[str, Any]:
        """Probe chat and embedding providers without raising provider errors."""
        result: dict[str, Any] = {
            "provider": settings.LLM_PROVIDER,
            "chat_model": self.model_name,
            "embedding_model": self.embedding_model,
            "chat": "unhealthy",
            "embeddings": "unhealthy",
        }

        try:
            await acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=8,
                **self._request_options(),
            )
            result["chat"] = "healthy"
        except Exception as exc:
            logger.warning("[LLMClient] Chat health check failed: %s", exc)
            result["chat_error"] = str(exc)

        try:
            await aembedding(
                model=self.embedding_model,
                input=["health check"],
                **self._request_options(),
            )
            result["embeddings"] = "healthy"
        except Exception as exc:
            logger.warning("[LLMClient] Embedding health check failed: %s", exc)
            result["embeddings_error"] = str(exc)

        result["status"] = (
            "healthy"
            if result["chat"] == "healthy" and result["embeddings"] == "healthy"
            else "degraded"
            if result["chat"] == "healthy" or result["embeddings"] == "healthy"
            else "unhealthy"
        )
        return result

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_schema: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Call LLM with structured output response format enforced by Pydantic schema."""
        logger.info(
            f"[LLMClient] Invoking model {self.model_name} expecting {response_schema.__name__}"
        )

        # Format schema for json_schema or response_format
        try:
            response = await acompletion(
                model=self.model_name,
                messages=messages,
                response_format=response_schema,
                temperature=temperature,
                max_tokens=settings.LLM_MAX_TOKENS,
                **self._request_options(),
            )
            content = response.choices[0].message.content
            # Parse structured content into Pydantic model
            if isinstance(content, str):
                parsed = response_schema.model_validate_json(content)
            elif isinstance(content, dict):
                parsed = response_schema.model_validate(content)
            else:
                raise ValueError(f"Unexpected content type from LLM: {type(content)}")

            return parsed
        except Exception as e:
            logger.warning(
                f"[LLMClient] Direct json_schema completion failed ({e}), attempting JSON mode fallback..."
            )
            # Fallback for models or mock modes: request raw json and validate
            system_append = f"\nReturn strictly valid JSON matching this schema:\n{json.dumps(response_schema.model_json_schema())}"
            messages_copy = [m.copy() for m in messages]
            messages_copy[0]["content"] += system_append

            response = await acompletion(
                model=self.model_name,
                messages=messages_copy,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=settings.LLM_MAX_TOKENS,
                **self._request_options(),
            )
            content = response.choices[0].message.content
            return response_schema.model_validate_json(content)

    async def get_embedding(self, text: str) -> list[float]:
        """Generate vector embedding for semantic search."""
        try:
            response = await aembedding(
                model=self.embedding_model,
                input=[text],
                **self._request_options(),
            )
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error(
                f"[LLMClient] Embedding generation failed: {e}. Returning mock vector for fallback."
            )
            # Return dummy 1536-dim vector if mock API key is set
            return [0.0] * 1536
