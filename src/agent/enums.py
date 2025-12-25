"""Enumerations for the AI agent module."""

from enum import StrEnum


class RiskLevel(StrEnum):
    """Risk classification for tool operations.

    Safe tools perform read-only or additive actions.
    Sensitive tools perform destructive or irreversible actions.
    """

    SAFE = "safe"
    SENSITIVE = "sensitive"
