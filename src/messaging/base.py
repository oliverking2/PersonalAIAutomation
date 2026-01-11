"""Base classes for messaging platforms.

Provides abstract interfaces for message formatting that allow swapping
messaging platforms (e.g., Telegram → MS Teams) without changing call sites.
"""

from abc import ABC, abstractmethod


class MessageFormatter(ABC):
    """Abstract base class for message formatters.

    Implementations convert standard Markdown to platform-specific formats.
    This abstraction allows swapping messaging platforms without changing call sites.
    """

    @abstractmethod
    def format(self, markdown: str) -> tuple[str, str]:
        """Convert Markdown text to platform-specific format.

        :param markdown: Standard Markdown text (e.g., from LLM output).
        :returns: Tuple of (formatted_text, parse_mode).
        """
        ...
