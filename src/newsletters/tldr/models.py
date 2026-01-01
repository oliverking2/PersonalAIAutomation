"""Pydantic models for parsed newsletter data."""

from pydantic import HttpUrl

from src.enums import NewsletterType
from src.newsletters.base.models import ParsedArticleBase, ParsedDigestBase


class ParsedArticle(ParsedArticleBase):
    """An article extracted from a TLDR newsletter."""

    url_parsed: HttpUrl


class ParsedNewsletter(ParsedDigestBase):
    """A parsed TLDR newsletter with extracted articles."""

    newsletter_type: NewsletterType
    articles: list[ParsedArticle]
