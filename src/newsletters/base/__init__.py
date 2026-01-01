"""Base classes and utilities for newsletter processing."""

from src.newsletters.base.fetcher import extract_email_metadata, fetch_emails, parse_datetime
from src.newsletters.base.models import ParsedArticleBase, ParsedDigestBase, ProcessingResult
from src.newsletters.base.service import BaseNewsletterService

__all__ = [
    "BaseNewsletterService",
    "ParsedArticleBase",
    "ParsedDigestBase",
    "ProcessingResult",
    "extract_email_metadata",
    "fetch_emails",
    "parse_datetime",
]
