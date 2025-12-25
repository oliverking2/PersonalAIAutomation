"""Tool registry for the AI agent module."""

import logging
from typing import Any

from src.agent.enums import RiskLevel
from src.agent.exceptions import DuplicateToolError, ToolNotFoundError
from src.agent.models import ToolDef, ToolMetadata
from src.agent.tools import get_goals_tools, get_reading_list_tools, get_tasks_tools

logger = logging.getLogger(__name__)


def create_default_registry() -> "ToolRegistry":
    """Create a tool registry with all default tools registered.

    This is the recommended way to get a fully configured registry
    with all available tools.

    :returns: ToolRegistry instance with all tools registered.
    """
    registry = ToolRegistry()

    # Register all tool groups
    for tool in get_reading_list_tools():
        registry.register(tool)

    for tool in get_goals_tools():
        registry.register(tool)

    for tool in get_tasks_tools():
        registry.register(tool)

    logger.info(f"Created default registry with {len(registry)} tools")
    return registry


class ToolRegistry:
    """Central registry for all available tools.

    Manages tool registration, lookup, and filtering. Each tool must have
    a unique name. The registry validates uniqueness at registration time.
    """

    def __init__(self) -> None:
        """Initialise an empty tool registry."""
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        """Register a tool in the registry.

        :param tool: Tool definition to register.
        :raises DuplicateToolError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: name={tool.name}, risk_level={tool.risk_level}")

    def get(self, name: str) -> ToolDef:
        """Retrieve a tool by name.

        :param name: Name of the tool to retrieve.
        :returns: The tool definition.
        :raises ToolNotFoundError: If the tool is not found.
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def get_many(self, names: list[str]) -> list[ToolDef]:
        """Retrieve multiple tools by name.

        :param names: List of tool names to retrieve.
        :returns: List of tool definitions in the same order as names.
        :raises ToolNotFoundError: If any tool is not found.
        """
        return [self.get(name) for name in names]

    def list_all(self) -> list[ToolDef]:
        """List all registered tools.

        :returns: List of all tool definitions.
        """
        return list(self._tools.values())

    def list_metadata(self) -> list[ToolMetadata]:
        """List metadata for all registered tools.

        Useful for tool selection without exposing full tool definitions.

        :returns: List of tool metadata.
        """
        return [
            ToolMetadata(
                name=tool.name,
                description=tool.description,
                tags=tool.tags,
                risk_level=tool.risk_level,
            )
            for tool in self._tools.values()
        ]

    def filter_by_tags(self, tags: set[str]) -> list[ToolDef]:
        """Filter tools by tags.

        Returns tools that have at least one matching tag.

        :param tags: Set of tags to filter by.
        :returns: List of matching tool definitions.
        """
        return [tool for tool in self._tools.values() if tool.tags & tags]

    def filter_by_risk_level(self, risk_level: RiskLevel) -> list[ToolDef]:
        """Filter tools by risk level.

        :param risk_level: Risk level to filter by.
        :returns: List of matching tool definitions.
        """
        return [tool for tool in self._tools.values() if tool.risk_level == risk_level]

    def to_bedrock_tool_config(self, tool_names: list[str]) -> dict[str, Any]:
        """Generate Bedrock toolConfig for specified tools.

        :param tool_names: Names of tools to include in the config.
        :returns: Bedrock-compatible toolConfig dictionary.
        :raises ToolNotFoundError: If any tool is not found.
        """
        tools = self.get_many(tool_names)
        return {"tools": [tool.to_bedrock_tool_spec() for tool in tools]}

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
