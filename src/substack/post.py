"""Substack post API wrapper."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import requests

from src.substack.constants import DEFAULT_HEADERS, DEFAULT_TIMEOUT

if TYPE_CHECKING:
    from src.substack.client import SubstackClient

logger = logging.getLogger(__name__)


class Post:
    """Represents a Substack post.

    Provides access to post content and metadata.
    """

    def __init__(self, url: str, *, client: SubstackClient | None = None) -> None:
        """Initialise a Post object.

        :param url: The URL of the Substack post.
        :param client: Optional authenticated client for paywalled content.
        """
        self.url = url
        self.client = client

        parsed_url = urlparse(url)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        path_parts = parsed_url.path.strip("/").split("/")
        self.slug = path_parts[-1] if path_parts else None

        self._post_data: dict[str, Any] | None = None

    def __str__(self) -> str:
        """Return string representation."""
        return f"Post: {self.url}"

    def __repr__(self) -> str:
        """Return repr string."""
        return f"Post(url={self.url!r})"

    @property
    def _endpoint(self) -> str:
        """Get the API endpoint for this post."""
        return f"{self.base_url}/api/v1/posts/{self.slug}"

    def _fetch_post_data(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch post data from the API with caching.

        :param force_refresh: Whether to bypass the cache.
        :returns: Full post metadata.
        :raises requests.HTTPError: If the request fails.
        """
        if self._post_data is not None and not force_refresh:
            return self._post_data

        if self.client and self.client.authenticated:
            r = self.client.get(self._endpoint, timeout=DEFAULT_TIMEOUT)
        else:
            r = requests.get(self._endpoint, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)

        r.raise_for_status()
        self._post_data = r.json()
        return self._post_data

    def get_metadata(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Get full post metadata.

        :param force_refresh: Whether to bypass the cache.
        :returns: Full post metadata dictionary.
        """
        return self._fetch_post_data(force_refresh=force_refresh)

    def get_content(self, *, force_refresh: bool = False) -> str | None:
        """Get the HTML content of the post.

        :param force_refresh: Whether to bypass the cache.
        :returns: HTML content, or None if not available (e.g., paywalled).
        """
        data = self._fetch_post_data(force_refresh=force_refresh)
        content = data.get("body_html")

        if not content and self.is_paywalled and not self.client:
            logger.warning(f"Post is paywalled and no auth provided: {self.url}")

        return content

    @property
    def is_paywalled(self) -> bool:
        """Check if the post is paywalled.

        :returns: True if post is only for paid subscribers.
        """
        data = self._fetch_post_data()
        return data.get("audience") == "only_paid"

    @property
    def title(self) -> str:
        """Get the post title.

        :returns: The post title.
        """
        return self._fetch_post_data()["title"]

    @property
    def subtitle(self) -> str | None:
        """Get the post subtitle.

        :returns: The post subtitle, or None if not set.
        """
        return self._fetch_post_data().get("subtitle")

    @property
    def publication_id(self) -> int:
        """Get the publication ID.

        :returns: The ID of the publication this post belongs to.
        """
        return self._fetch_post_data()["publication_id"]
