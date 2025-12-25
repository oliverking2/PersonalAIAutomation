"""AI Agent module for tool-based LLM interactions.

This module provides a reusable agent runtime built on AWS Bedrock Converse
with structured tool calling, validation, and safety guardrails.
"""

from src.agent.client import BedrockClient
from src.agent.enums import RiskLevel
from src.agent.exceptions import (
    AgentError,
    BedrockClientError,
    DuplicateToolError,
    ToolNotFoundError,
    ToolRegistryError,
    ToolSelectionError,
)
from src.agent.models import ToolDef, ToolMetadata, ToolSelectionResult
from src.agent.registry import ToolRegistry
from src.agent.selector import ToolSelector

__all__ = [
    "AgentError",
    "BedrockClient",
    "BedrockClientError",
    "DuplicateToolError",
    "RiskLevel",
    "ToolDef",
    "ToolMetadata",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolSelectionError",
    "ToolSelectionResult",
    "ToolSelector",
]
