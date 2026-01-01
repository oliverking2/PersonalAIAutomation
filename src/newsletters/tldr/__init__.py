"""TLDR newsletter processing module."""

from src.enums import NewsletterType
from src.newsletters.tldr.fetcher import TLDR_SENDER_EMAIL, fetch_tldr_newsletters
from src.newsletters.tldr.models import ParsedArticle, ParsedNewsletter
from src.newsletters.tldr.parser import parse_newsletter_html
from src.newsletters.tldr.service import TLDRService

__all__ = [
    "TLDR_SENDER_EMAIL",
    "NewsletterType",
    "ParsedArticle",
    "ParsedNewsletter",
    "TLDRService",
    "fetch_tldr_newsletters",
    "parse_newsletter_html",
]
