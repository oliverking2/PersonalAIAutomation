"""Enumerations for the AI agent module."""

from enum import StrEnum


class RiskLevel(StrEnum):
    """Risk classification for tool operations.

    Safe tools perform read-only or additive actions.
    Sensitive tools perform destructive or irreversible actions.
    """

    SAFE = "safe"
    SENSITIVE = "sensitive"


class CallType(StrEnum):
    """Type of LLM call for tracking purposes."""

    CHAT = "chat"
    SELECTOR = "selector"
    CLASSIFIER = "classifier"
    SUMMARISER = "summariser"


class ConfirmationType(StrEnum):
    """Classification of user response to a confirmation request.

    CONFIRM: User agreed to proceed with all actions.
    DENY: User declined the actions.
    NEW_INTENT: User's message is a new request, not a confirmation response.
    PARTIAL_CONFIRM: User approved some actions but not all, or provided corrections.
    """

    CONFIRM = "confirm"
    DENY = "deny"
    NEW_INTENT = "new_intent"
    PARTIAL_CONFIRM = "partial_confirm"


class ToolDecisionType(StrEnum):
    """Decision type for individual tools in a batch confirmation.

    APPROVE: User approved this tool to execute as-is.
    REJECT: User rejected this tool.
    MODIFY: User wants to modify the tool's arguments.
    """

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
