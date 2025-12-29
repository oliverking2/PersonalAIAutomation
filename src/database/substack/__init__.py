"""Substack database models and operations."""

from src.database.substack.models import SubstackNewsletter, SubstackPost
from src.database.substack.operations import (
    SubstackPostData,
    create_substack_post,
    ensure_newsletters_exist,
    get_or_create_newsletter,
    get_substack_newsletter_by_url,
    get_unsent_substack_posts,
    mark_substack_post_alerted,
    substack_post_exists,
)

__all__ = [
    "SubstackNewsletter",
    "SubstackPost",
    "SubstackPostData",
    "create_substack_post",
    "ensure_newsletters_exist",
    "get_or_create_newsletter",
    "get_substack_newsletter_by_url",
    "get_unsent_substack_posts",
    "mark_substack_post_alerted",
    "substack_post_exists",
]
