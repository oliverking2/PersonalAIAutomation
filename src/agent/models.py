"""Pydantic models for the AI agent module."""

from collections.abc import Callable
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
