"""Substack API client library.

This module provides classes for interacting with Substack's API:
- Newsletter: Access posts, authors, and recommendations for a publication
- Post: Access post content and metadata
- User: Access user profiles and subscriptions
- Category: Browse newsletters by category
- SubstackClient: Authenticated HTTP client for paywalled content
"""

from src.substack.client import SubstackClient
from src.substack.newsletter import Newsletter
from src.substack.newsletter_category import Category, list_all_categories
from src.substack.post import Post
from src.substack.user import User

__all__ = [
    "Category",
    "Newsletter",
    "Post",
    "SubstackClient",
    "User",
    "list_all_categories",
]
