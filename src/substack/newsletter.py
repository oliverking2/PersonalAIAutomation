"""Substack newsletter API wrapper."""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any

import requests

from src.substack.client import SubstackClient
from src.substack.constants import DEFAULT_PAGE_SIZE, DISCOVERY_HEADERS, SEARCH_URL
from src.substack.post import Post
from src.substack.user import User

logger = logging.getLogger(__name__)

# Module-level client for public API requests
_client = SubstackClient()


def _host_from_url(url: str) -> str:
    """Extract hostname from URL.

    :param url: URL to parse (with or without scheme).
    :returns: Lowercase hostname.
    """
    full_url = url if "://" in url else f"https://{url}"
    return urllib.parse.urlparse(full_url).netloc.lower()


def _match_publication(search_results: dict[str, Any], host: str) -> dict[str, Any] | None:
    """Match a publication from search results by hostname.

    Tries exact custom domain match, then subdomain match.

    :param search_results: API search results.
    :param host: Target hostname to match.
    :returns: Matching publication dict, or None if not found.
    """
    for item in search_results.get("publications", []):
        custom_domain = item.get("custom_domain")
        subdomain = item.get("subdomain")

        if custom_domain and _host_from_url(custom_domain) == host:
            return item
        if subdomain and f"{subdomain.lower()}.substack.com" == host:
            return item

    # Fallback: loose match on subdomain token
    match = re.match(r"^([a-z0-9-]+)\.substack\.com$", host)
    if match:
        sub = match.group(1)
        for item in search_results.get("publications", []):
            if item.get("subdomain", "").lower() == sub:
                return item

    return None


class Newsletter:
    """Represents a Substack newsletter/publication.

    Provides access to posts, authors, and recommendations.
    """

    def __init__(self, url: str, *, client: SubstackClient | None = None) -> None:
        """Initialise a Newsletter object.

        :param url: The base URL of the Substack newsletter.
        :param client: Optional client for authenticated requests.
        """
        self.url = url.rstrip("/")
        self._client = client or _client
        logger.debug(f"Initialised Newsletter: {self.url}")

    def __str__(self) -> str:
        """Return string representation."""
        return f"Newsletter: {self.url}"

    def __repr__(self) -> str:
        """Return repr string."""
        return f"Newsletter(url={self.url!r})"

    def _fetch_paginated_posts(
        self,
        params: dict[str, str],
        limit: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Fetch posts with pagination.

        :param params: Query parameters for the API request.
        :param limit: Maximum number of posts to return.
        :param page_size: Number of posts per page.
        :returns: List of post data dictionaries.
        """
        results: list[dict[str, Any]] = []
        offset = 0

        logger.debug(f"Fetching posts with params: {params}, limit: {limit}")

        endpoint = f"{self.url}/api/v1/archive"

        while True:
            current_params = {
                **params,
                "offset": str(offset),
                "limit": str(page_size),
            }

            items = self._client.get_json(endpoint, params=current_params)
            if not items:
                break

            results.extend(items)
            offset += page_size
            logger.debug(f"Fetched {len(results)} posts so far")

            if limit and len(results) >= limit:
                return results[:limit]

            if len(items) < page_size:
                break

        logger.info(f"Fetched {len(results)} posts from {self.url}")
        return results

    def get_posts(
        self,
        sorting: str = "new",
        limit: int | None = None,
    ) -> list[Post]:
        """Get posts from the newsletter.

        :param sorting: Sort order ("new", "top", "pinned", or "community").
        :param limit: Maximum number of posts to return.
        :returns: List of Post objects.
        """
        logger.info(f"Getting posts from {self.url} (sorting={sorting}, limit={limit})")
        post_data = self._fetch_paginated_posts({"sort": sorting}, limit)
        return [Post(item["canonical_url"], client=self._client) for item in post_data]

    def search_posts(self, query: str, limit: int | None = None) -> list[Post]:
        """Search posts in the newsletter.

        :param query: Search query string.
        :param limit: Maximum number of posts to return.
        :returns: List of matching Post objects.
        """
        logger.info(f"Searching posts in {self.url} for: {query}")
        post_data = self._fetch_paginated_posts({"sort": "new", "search": query}, limit)
        return [Post(item["canonical_url"], client=self._client) for item in post_data]

    def get_podcasts(self, limit: int | None = None) -> list[Post]:
        """Get podcast episodes from the newsletter.

        :param limit: Maximum number of podcasts to return.
        :returns: List of Post objects for podcast episodes.
        """
        logger.info(f"Getting podcasts from {self.url}")
        post_data = self._fetch_paginated_posts({"sort": "new", "type": "podcast"}, limit)
        return [Post(item["canonical_url"], client=self._client) for item in post_data]

    def _resolve_publication_id(self) -> int | None:
        """Resolve publication ID via Substack discovery search.

        :returns: The publication ID, or None if not found.
        """
        host = _host_from_url(self.url)
        query = host.split(":")[0]  # Strip port if present

        logger.debug(f"Resolving publication ID for: {host}")

        params: dict[str, str | int] = {
            "query": query,
            "page": 0,
            "limit": 25,
            "skipExplanation": "true",
            "sort": "relevance",
        }

        # Use client with discovery headers
        data = self._client.get_json(SEARCH_URL, params=params, headers=DISCOVERY_HEADERS)
        match = _match_publication(data, host)
        if match:
            pub_id = match.get("id")
            logger.debug(f"Resolved publication ID: {pub_id}")
            return pub_id

        logger.debug(f"Could not resolve publication ID for: {host}")
        return None

    def get_recommendations(self) -> list[Newsletter]:
        """Get recommended publications.

        :returns: List of recommended Newsletter objects.
        """
        logger.info(f"Getting recommendations for {self.url}")
        publication_id = self._resolve_publication_id()

        if not publication_id:
            # Fallback: try to get ID from a post
            try:
                posts = self.get_posts(limit=1)
                if posts:
                    publication_id = posts[0].publication_id
            except requests.RequestException:
                logger.warning(f"Failed to resolve publication ID for {self.url}")

        if not publication_id:
            logger.warning(f"No publication ID found for {self.url}")
            return []

        endpoint = f"{self.url}/api/v1/recommendations/from/{publication_id}"
        recommendations = self._client.get_json(endpoint) or []

        urls: list[str] = []
        for rec in recommendations:
            pub = rec.get("recommendedPublication", {})
            if pub.get("custom_domain"):
                urls.append(f"https://{pub['custom_domain']}")
            elif pub.get("subdomain"):
                urls.append(f"https://{pub['subdomain']}.substack.com")

        logger.info(f"Found {len(urls)} recommendations for {self.url}")
        return [Newsletter(u, client=self._client) for u in urls]

    def get_authors(self) -> list[User]:
        """Get authors of the newsletter.

        :returns: List of User objects for the authors.
        """
        logger.info(f"Getting authors for {self.url}")
        endpoint = f"{self.url}/api/v1/publication/users/ranked?public=true"
        authors = self._client.get_json(endpoint)
        logger.debug(f"Found {len(authors)} authors")
        return [User(author["handle"]) for author in authors]
