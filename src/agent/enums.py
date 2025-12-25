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

    CONFIRM: User agreed to proceed with the action.
    DENY: User declined the action.
    NEW_INTENT: User's message is a new request, not a confirmation response.
    """

    CONFIRM = "confirm"
    DENY = "deny"
    NEW_INTENT = "new_intent"
