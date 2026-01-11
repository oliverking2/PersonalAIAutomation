"""Tool registry for the AI agent module."""

import logging
from typing import Any

from src.agent.enums import RiskLevel
from src.agent.exceptions import DomainSizeError, DuplicateToolError, ToolNotFoundError
from src.agent.models import ToolDef
from src.agent.tools import (
    get_goals_tools,
    get_ideas_tools,
    get_memory_tools,
    get_reading_list_tools,
    get_reminders_tools,
    get_tasks_tools,
)

# Maximum tools per domain - must be <= DEFAULT_MAX_TOOLS in selector
MAX_TOOLS_PER_DOMAIN = 10

logger = logging.getLogger(__name__)


def create_default_registry() -> "ToolRegistry":
    """Create a tool registry with all default tools registered.

    This is the recommended way to get a fully configured registry
    with all available tools.

    :returns: ToolRegistry instance with all tools registered.
    """
    registry = ToolRegistry()

    # Register system tools (always available)
    for tool in get_memory_tools():
        registry.register(tool)

    # Register all tool groups
    for tool in get_reading_list_tools():
        registry.register(tool)

    for tool in get_goals_tools():
        registry.register(tool)

    for tool in get_tasks_tools():
        registry.register(tool)

    for tool in get_ideas_tools():
        registry.register(tool)

    for tool in get_reminders_tools():
        registry.register(tool)

    # Validate no domain exceeds max tool limit
    registry.validate_domain_sizes()

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

    def get_system_tools(self) -> list[ToolDef]:
        """Get tools tagged as 'system'.

        System tools are always available and bypass normal tool selection.
        They are core agent capabilities like memory management.

        :returns: List of system tool definitions.
        """
        return self.filter_by_tags({"system"})

    def get_selectable_tools(self) -> list[ToolDef]:
        """Get tools that are NOT tagged as 'system'.

        These are domain-specific tools that should be selected per-request
        by the ToolSelector based on user intent.

        :returns: List of selectable (non-system) tool definitions.
        """
        return [tool for tool in self._tools.values() if "system" not in tool.tags]

    def to_bedrock_tool_config_with_cache_points(
        self,
        domains: list[str],
    ) -> dict[str, Any]:
        """Generate Bedrock toolConfig with cache points after each domain.

        System tools are always included first, followed by domain tools.
        Groups tools by domain and adds a cachePoint after each domain's tools.
        This enables incremental caching - when a new domain is added, only
        the new domain's tools need to be cache-written while previous domains
        are cache-read.

        :param domains: Ordered list of domains (order determines cache point placement).
        :returns: Bedrock-compatible toolConfig with cache points.
        """
        tools_list: list[dict[str, Any]] = []

        # Always include system tools first (e.g., memory tools)
        system_tools = self.get_system_tools()
        if system_tools:
            for tool in system_tools:
                tools_list.append(tool.to_bedrock_tool_spec())
            # Add cache point after system tools for stable caching
            tools_list.append({"cachePoint": {"type": "default"}})

        for domain in domains:
            # Get all tools for this domain
            domain_tools = [tool for tool in self._tools.values() if domain in tool.tags]

            # Add tool specs for this domain
            for tool in domain_tools:
                tools_list.append(tool.to_bedrock_tool_spec())

            # Add cache point after this domain's tools (if we added any tools)
            if domain_tools:
                tools_list.append({"cachePoint": {"type": "default"}})

        return {"tools": tools_list}

    def get_domains(self) -> set[str]:
        """Get all unique domain tags from registered tools.

        Domain tags have the format 'domain:{name}' (e.g., 'domain:tasks').

        :returns: Set of unique domain tags.
        """
        domains: set[str] = set()
        for tool in self._tools.values():
            for tag in tool.tags:
                if tag.startswith("domain:"):
                    domains.add(tag)
        return domains

    def get_tools_by_domain(self, domain_tag: str) -> list[ToolDef]:
        """Get all tools for a specific domain.

        :param domain_tag: Domain tag (e.g., 'domain:tasks').
        :returns: List of tools in that domain.
        """
        return [tool for tool in self._tools.values() if domain_tag in tool.tags]

    def get_domain_tool_count(self) -> dict[str, int]:
        """Get count of tools per domain.

        :returns: Dictionary mapping domain tags to tool counts.
        """
        counts: dict[str, int] = {}
        for tool in self._tools.values():
            for tag in tool.tags:
                if tag.startswith("domain:"):
                    counts[tag] = counts.get(tag, 0) + 1
        return counts

    def validate_domain_sizes(self, max_tools: int = MAX_TOOLS_PER_DOMAIN) -> None:
        """Validate that no domain exceeds the maximum tool count.

        This should be called after all tools are registered to catch
        configuration errors early before the agent starts.

        :param max_tools: Maximum allowed tools per domain.
        :raises DomainSizeError: If any domain exceeds the limit.
        """
        counts = self.get_domain_tool_count()
        for domain, count in counts.items():
            if count > max_tools:
                raise DomainSizeError(domain, count, max_tools)
        logger.debug(f"Domain sizes validated: {counts}")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
