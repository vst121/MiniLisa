"""
Tool Registry for managing and looking up agent tools.
"""

from typing import Dict, List, Optional
from src.tools.base import BaseTool


class ToolRegistry:
    """Registry maintaining available tools for agents."""

    def __init__(self, tools: Optional[List[BaseTool]] = None) -> None:
        self._tools: Dict[str, BaseTool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Look up tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_json_schemas(self) -> List[Dict]:
        """Generate JSON schemas for all registered tools."""
        return [tool.get_json_schema() for tool in self._tools.values()]
