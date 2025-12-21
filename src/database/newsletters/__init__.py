"""Newsletter database models and operations."""

from src.database.newsletters.models import Article, Newsletter
from src.database.newsletters.operations import (
    BackfillResult,
    article_exists,
    backfill_article_urls,
    compute_url_hash,
    create_newsletter,
    get_newsletter_by_id,
    get_unsent_newsletters,
    mark_newsletter_alerted,
    newsletter_exists,
)

__all__ = [
    "Article",
    "BackfillResult",
    "Newsletter",
    "article_exists",
    "backfill_article_urls",
    "compute_url_hash",
    "create_newsletter",
    "get_newsletter_by_id",
    "get_unsent_newsletters",
    "mark_newsletter_alerted",
    "newsletter_exists",
]
