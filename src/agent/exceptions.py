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
