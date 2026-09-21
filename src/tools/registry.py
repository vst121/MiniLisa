"""
Tool Registry for managing and looking up agent tools.
"""

from src.tools.base import BaseTool


class ToolRegistry:
    """Registry maintaining available tools for agents."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        """Look up tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> list[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_json_schemas(self) -> list[dict]:
        """Generate JSON schemas for all registered tools."""
        return [tool.get_json_schema() for tool in self._tools.values()]
