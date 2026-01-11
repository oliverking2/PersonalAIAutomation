"""Messaging module providing platform-agnostic abstractions.

This module defines base classes for message formatting that allow
swapping messaging platforms without changing call sites.
"""

from src.messaging.base import MessageFormatter

__all__ = [
    "MessageFormatter",
]
