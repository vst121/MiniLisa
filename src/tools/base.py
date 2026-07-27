"""
Base Agent Tool Module.
Provides abstract BaseTool interface for typed, testable agent tools.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type
from pydantic import BaseModel


class BaseTool(ABC):
    """Abstract Base Tool for Agent execution."""

    name: str
    description: str
    args_schema: Type[BaseModel]

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute tool logic asynchronously."""
        pass

    def get_json_schema(self) -> Dict[str, Any]:
        """Generate JSON schema representation for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema.model_json_schema(),
        }
