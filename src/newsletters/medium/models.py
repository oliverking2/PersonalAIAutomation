"""Pydantic models for parsed Medium Daily Digest data."""

from src.newsletters.base.models import ParsedArticleBase, ParsedDigestBase


class ParsedMediumArticle(ParsedArticleBase):
    """An article extracted from a Medium Daily Digest email."""

    read_time_minutes: int | None = None


class ParsedMediumDigest(ParsedDigestBase):
    """A parsed Medium Daily Digest with extracted articles."""

    articles: list[ParsedMediumArticle]
