"""Central enum definitions for the project."""

from enum import StrEnum


class ExtractionSource(StrEnum):
    """Identifiers for extraction sources used in watermark tracking."""

    NEWSLETTER_TLDR = "newsletter:tldr"
    NEWSLETTER_MEDIUM = "newsletter:medium"
    SUBSTACK = "substack"


class NewsletterType(StrEnum):
    """Type of TLDR newsletter."""

    TLDR = "TLDR"
    TLDR_AI = "TLDR AI"
    TLDR_DEV = "TLDR Dev"
    TLDR_DATA = "TLDR Data"
