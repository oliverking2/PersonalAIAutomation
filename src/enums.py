"""Central enum definitions for the project."""

from enum import StrEnum


class ExtractionSource(StrEnum):
    """Identifiers for extraction sources used in watermark tracking."""

    NEWSLETTER_TLDR = "newsletter:tldr"
    SUBSTACK = "substack"
