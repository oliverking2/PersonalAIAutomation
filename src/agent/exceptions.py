"""Custom exceptions for the AI agent module."""


class AgentError(Exception):
    """Base exception for agent-related errors."""


class ToolRegistryError(AgentError):
    """Error related to tool registration or lookup."""


class DuplicateToolError(ToolRegistryError):
    """Raised when attempting to register a tool with a duplicate name."""

    def __init__(self, tool_name: str) -> None:
        """Initialise DuplicateToolError.

        :param tool_name: Name of the duplicate tool.
        """
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' is already registered")


class ToolNotFoundError(ToolRegistryError):
    """Raised when a requested tool is not found in the registry."""

    def __init__(self, tool_name: str) -> None:
        """Initialise ToolNotFoundError.

        :param tool_name: Name of the missing tool.
        """
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' not found in registry")


class BedrockClientError(AgentError):
    """Error related to AWS Bedrock API calls."""


class ToolSelectionError(AgentError):
    """Error during tool selection process."""
