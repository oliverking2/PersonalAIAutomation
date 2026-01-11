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


class DomainSizeError(ToolRegistryError):
    """Raised when a domain has too many tools."""

    def __init__(self, domain: str, tool_count: int, max_tools: int) -> None:
        """Initialise DomainSizeError.

        :param domain: The domain that exceeds the limit.
        :param tool_count: Number of tools in the domain.
        :param max_tools: Maximum allowed tools per domain.
        """
        self.domain = domain
        self.tool_count = tool_count
        self.max_tools = max_tools
        super().__init__(f"Domain '{domain}' has {tool_count} tools, exceeds max of {max_tools}")


class BedrockClientError(AgentError):
    """Error related to AWS Bedrock API calls."""


class BedrockResponseError(AgentError):
    """Raised when Bedrock API response is malformed or missing required fields."""

    def __init__(
        self,
        message: str,
        response: dict[str, object] | None = None,
        field: str | None = None,
    ) -> None:
        """Initialise Bedrock response error.

        :param message: Human-readable error description.
        :param response: Raw response that caused the error (for debugging).
        :param field: Specific field that was missing or invalid.
        """
        super().__init__(message)
        self.response = response
        self.field = field

    def __str__(self) -> str:
        """Return string representation with field context if available."""
        base = super().__str__()
        if self.field:
            return f"{base} (field: {self.field})"
        return base


class ToolSelectionError(AgentError):
    """Error during tool selection process."""


class MaxStepsExceededError(AgentError):
    """Raised when the agent exceeds the maximum number of tool execution steps."""

    def __init__(self, max_steps: int, steps_taken: int) -> None:
        """Initialise MaxStepsExceededError.

        :param max_steps: Maximum steps allowed.
        :param steps_taken: Number of steps taken before hitting limit.
        """
        self.max_steps = max_steps
        self.steps_taken = steps_taken
        super().__init__(f"Agent exceeded maximum steps: max={max_steps}, taken={steps_taken}")


class ToolExecutionError(AgentError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, error: str) -> None:
        """Initialise ToolExecutionError.

        :param tool_name: Name of the tool that failed.
        :param error: Error message from the tool.
        """
        self.tool_name = tool_name
        self.error = error
        super().__init__(f"Tool '{tool_name}' execution failed: {error}")


class ToolTimeoutError(AgentError):
    """Raised when tool execution exceeds configured timeout."""

    def __init__(self, tool_name: str, timeout_seconds: float) -> None:
        """Initialise ToolTimeoutError.

        :param tool_name: Name of the tool that timed out.
        :param timeout_seconds: The timeout value that was exceeded.
        """
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Tool '{tool_name}' exceeded {timeout_seconds}s timeout")
