"""AI Agent module for tool-based LLM interactions.

This module provides a reusable agent runtime built on AWS Bedrock Converse
with structured tool calling, validation, and safety guardrails.
"""

from src.agent.bedrock_client import MODEL_ALIASES, BedrockClient, resolve_model_id
from src.agent.enums import RiskLevel
from src.agent.exceptions import (
    AgentError,
    BedrockClientError,
    DuplicateToolError,
    MaxStepsExceededError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistryError,
    ToolSelectionError,
)
from src.agent.models import (
    AgentRunResult,
    ConfirmationRequest,
    ToolCall,
    ToolDef,
    ToolMetadata,
    ToolSelectionResult,
)
from src.agent.runner import AgentRunner
from src.agent.utils.config import DEFAULT_AGENT_CONFIG, MODEL_PRICING, AgentConfig, ModelPricing
from src.agent.utils.tools.registry import ToolRegistry, create_default_registry
from src.agent.utils.tools.selector import ToolSelector

__all__ = [
    "DEFAULT_AGENT_CONFIG",
    "MODEL_ALIASES",
    "MODEL_PRICING",
    "AgentConfig",
    "AgentError",
    "AgentRunResult",
    "AgentRunner",
    "BedrockClient",
    "BedrockClientError",
    "ConfirmationRequest",
    "DuplicateToolError",
    "MaxStepsExceededError",
    "ModelPricing",
    "RiskLevel",
    "ToolCall",
    "ToolDef",
    "ToolExecutionError",
    "ToolMetadata",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolSelectionError",
    "ToolSelectionResult",
    "ToolSelector",
    "create_default_registry",
    "resolve_model_id",
]
