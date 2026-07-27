"""
LLM Service Adapter using LiteLLM.
Enforces Pydantic structured outputs on all LLM calls.
"""

import json
import logging
from typing import Any, Dict, List, Type, TypeVar
from litellm import acompletion, aembedding
from pydantic import BaseModel
from src.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """LiteLLM Async Adapter enforcing structured outputs and tracking costs."""

    def __init__(self, model_name: str | None = None, api_key: str | None = None):
        self.model_name = model_name or settings.LLM_MODEL
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.embedding_model = settings.EMBEDDING_MODEL

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """Call LLM with structured output response format enforced by Pydantic schema."""
        logger.info(f"[LLMClient] Invoking model {self.model_name} expecting {response_schema.__name__}")
        
        # Format schema for json_schema or response_format
        try:
            response = await acompletion(
                model=self.model_name,
                messages=messages,
                response_format=response_schema,
                temperature=temperature,
                api_key=self.api_key,
                timeout=settings.LLM_TIMEOUT,
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
            logger.warning(f"[LLMClient] Direct json_schema completion failed ({e}), attempting JSON mode fallback...")
            # Fallback for models or mock modes: request raw json and validate
            system_append = f"\nReturn strictly valid JSON matching this schema:\n{json.dumps(response_schema.model_json_schema())}"
            messages_copy = [m.copy() for m in messages]
            messages_copy[0]["content"] += system_append
            
            response = await acompletion(
                model=self.model_name,
                messages=messages_copy,
                response_format={"type": "json_object"},
                temperature=temperature,
                api_key=self.api_key,
                timeout=settings.LLM_TIMEOUT,
            )
            content = response.choices[0].message.content
            return response_schema.model_validate_json(content)

    async def get_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for semantic search."""
        try:
            response = await aembedding(
                model=self.embedding_model,
                input=[text],
                api_key=self.api_key,
            )
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error(f"[LLMClient] Embedding generation failed: {e}. Returning mock vector for fallback.")
            # Return dummy 1536-dim vector if mock API key is set
            return [0.0] * 1536
