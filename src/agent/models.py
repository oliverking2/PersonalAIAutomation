"""Pydantic models for the AI agent module."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.agent.enums import RiskLevel


class ToolDef(BaseModel):
    """Definition of a tool that can be invoked by the AI agent.

    :param name: Unique identifier for the tool.
    :param description: LLM-facing description of what the tool does.
    :param tags: Categories for filtering tools (e.g., 'reading', 'tasks').
    :param risk_level: Whether the tool is safe or sensitive.
    :param args_model: Pydantic model class defining the tool's arguments.
    :param handler: Function that executes the tool.
    """

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=1024)
    tags: frozenset[str] = Field(default_factory=frozenset)
    risk_level: RiskLevel = Field(default=RiskLevel.SAFE)
    args_model: type[BaseModel]
    handler: Callable[[Any], dict[str, Any]]

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    def to_json_schema(self) -> dict[str, Any]:
        """Generate JSON schema for the tool's arguments.

        :returns: JSON schema dictionary compatible with Bedrock Converse.
        """
        schema = self.args_model.model_json_schema()
        # Remove schema metadata not needed by Bedrock
        schema.pop("title", None)
        return schema

    def to_bedrock_tool_spec(self) -> dict[str, Any]:
        """Generate tool specification for AWS Bedrock Converse API.

        :returns: Tool specification dictionary for Bedrock toolConfig.
        """
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.to_json_schema()},
            }
        }


class ToolMetadata(BaseModel):
    """Lightweight metadata for tool selection.

    Used by the ToolSelector to decide which tools to expose.
    """

    name: str
    description: str
    tags: frozenset[str]
    risk_level: RiskLevel

    model_config = {"frozen": True}


class ToolSelectionResult(BaseModel):
    """Result of tool selection.

    :param tool_names: Ordered list of selected tool names.
    :param reasoning: Explanation for the selection (for debugging).
    """

    tool_names: list[str] = Field(default_factory=list)
    reasoning: str = Field(default="")


class ToolCall(BaseModel):
    """Record of a single tool call during agent execution.

    :param tool_use_id: Unique identifier for the tool use.
    :param tool_name: Name of the tool called.
    :param input_args: Input arguments passed to the tool.
    :param output: Output from the tool execution.
    :param is_error: Whether the tool execution resulted in an error.
    """

    tool_use_id: str
    tool_name: str
    input_args: dict[str, Any]
    output: dict[str, Any]
    is_error: bool = False


class PendingToolAction(BaseModel):
    """A single tool action pending confirmation.

    :param index: 1-based index for user display.
    :param tool_use_id: ID of the tool use block from the LLM.
    :param tool_name: Name of the tool.
    :param tool_description: Description of the tool.
    :param input_args: Arguments that would be passed to the tool.
    :param action_summary: Human-readable summary of what the tool would do.
    """

    index: int
    tool_use_id: str
    tool_name: str
    tool_description: str
    input_args: dict[str, Any]
    action_summary: str


class ConfirmationRequest(BaseModel):
    """Request for user confirmation before executing sensitive tools.

    Supports batch confirmation of multiple tools.

    :param tools: List of pending tool actions requiring confirmation.
    """

    tools: list[PendingToolAction]


class AgentRunResult(BaseModel):
    """Result of an agent run.

    :param response: Final text response from the agent.
    :param tool_calls: List of tool calls made during the run.
    :param steps_taken: Number of tool execution steps taken.
    :param stop_reason: Reason the agent stopped (end_turn, max_steps, confirmation_required).
    :param confirmation_request: If stop_reason is confirmation_required, contains details.
    """

    response: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    steps_taken: int = 0
    stop_reason: str = "end_turn"
    confirmation_request: ConfirmationRequest | None = None


class PendingConfirmation(BaseModel):
    """Serialisable pending confirmation state for persistence.

    This model is stored in the database as JSONB to preserve confirmation
    context between agent runs. Supports batch confirmation of multiple tools.

    :param tools: List of pending tool actions requiring confirmation.
    :param selected_tools: Tool names that were selected for this flow.
    """

    tools: list[PendingToolAction]
    selected_tools: list[str] = Field(default_factory=list)


@dataclass
class ConversationState:
    """Mutable state for a multi-run conversation.

    This dataclass holds the context that persists between agent runs,
    enabling stateful conversation handling including confirmation flows.
    """

    conversation_id: uuid.UUID
    messages: list[dict[str, Any]] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    pending_confirmation: PendingConfirmation | None = None
    summary: str | None = None
    message_count: int = 0
    last_summarised_at: datetime | None = None
