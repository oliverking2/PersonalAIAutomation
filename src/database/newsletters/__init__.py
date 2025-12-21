"""Newsletter database models and operations."""

from src.database.newsletters.models import Article, Newsletter
from src.database.newsletters.operations import (
    article_exists,
    compute_url_hash,
    create_newsletter,
    get_newsletter_by_id,
    get_unsent_newsletters,
    mark_newsletter_alerted,
    newsletter_exists,
)

__all__ = [
    "Article",
    "Newsletter",
    "article_exists",
    "compute_url_hash",
    "create_newsletter",
    "get_newsletter_by_id",
    "get_unsent_newsletters",
    "mark_newsletter_alerted",
    "newsletter_exists",
]
