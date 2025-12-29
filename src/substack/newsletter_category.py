"""Substack newsletter category API wrapper."""

from __future__ import annotations

import logging
from typing import Any

from src.substack.client import SubstackClient
from src.substack.constants import CATEGORIES_URL, MAX_CATEGORY_PAGES, SUBSTACK_BASE_URL

logger = logging.getLogger(__name__)

# Module-level client for public API requests (no auth needed)
_client = SubstackClient()


def list_all_categories() -> list[tuple[str, int]]:
    """Get all available newsletter categories.

    :returns: List of tuples containing (category_name, category_id).
    :raises requests.HTTPError: If the API request fails.
    """
    logger.debug("Fetching all categories")
    data = _client.get_json(CATEGORIES_URL)
    logger.info(f"Found {len(data)} categories")
    return [(item["name"], item["id"]) for item in data]


class Category:
    """Represents a Substack newsletter category.

    Categories group newsletters by topic (e.g., Technology, Culture).
    Returns URLs rather than Newsletter objects to avoid circular imports.
    Use Newsletter(url) to create Newsletter objects from the returned URLs.
    """

    def __init__(
        self,
        name: str | None = None,
        category_id: int | None = None,
        *,
        client: SubstackClient | None = None,
    ) -> None:
        """Initialise a Category object.

        Must provide either name or category_id.

        :param name: The category name.
        :param category_id: The category ID.
        :param client: Optional client for requests.
        :raises ValueError: If neither name nor category_id is provided,
            or if the provided value is not found.
        """
        if name is None and category_id is None:
            raise ValueError("Either name or category_id must be provided")

        self.name = name
        self.category_id = category_id
        self._client = client or _client
        self._newsletters_data: list[dict[str, Any]] | None = None

        if self.name and self.category_id is None:
            self._resolve_id_from_name()
        elif self.category_id and self.name is None:
            self._resolve_name_from_id()

        logger.debug(f"Initialised category: {self}")

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name} ({self.category_id})"

    def __repr__(self) -> str:
        """Return repr string."""
        return f"Category(name={self.name!r}, category_id={self.category_id})"

    def _resolve_id_from_name(self) -> None:
        """Look up category ID based on name.

        :raises ValueError: If the category name is not found.
        """
        logger.debug(f"Resolving category ID for name: {self.name}")
        categories = list_all_categories()
        for cat_name, cat_id in categories:
            if cat_name == self.name:
                self.category_id = cat_id
                logger.debug(f"Resolved {self.name} -> ID {cat_id}")
                return
        raise ValueError(f"Category name '{self.name}' not found")

    def _resolve_name_from_id(self) -> None:
        """Look up category name based on ID.

        :raises ValueError: If the category ID is not found.
        """
        logger.debug(f"Resolving category name for ID: {self.category_id}")
        categories = list_all_categories()
        for cat_name, cat_id in categories:
            if cat_id == self.category_id:
                self.name = cat_name
                logger.debug(f"Resolved ID {self.category_id} -> {cat_name}")
                return
        raise ValueError(f"Category ID {self.category_id} not found")

    def _fetch_newsletters_data(
        self,
        *,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch newsletter data from the API with caching.

        :param force_refresh: Whether to bypass the cache.
        :returns: List of newsletter metadata dictionaries.
        """
        if self._newsletters_data is not None and not force_refresh:
            logger.debug(f"Returning cached data for {self.name}")
            return self._newsletters_data

        endpoint = f"{SUBSTACK_BASE_URL}/api/v1/category/public/{self.category_id}/all"

        all_newsletters: list[dict[str, Any]] = []
        page_num = 0
        more = True

        logger.info(f"Fetching newsletters for category: {self.name}")

        while more and page_num < MAX_CATEGORY_PAGES:
            logger.debug(f"Fetching page {page_num}")
            data = self._client.get_json(endpoint, params={"page": page_num})
            all_newsletters.extend(data["publications"])
            page_num += 1
            more = data["more"]

        self._newsletters_data = all_newsletters
        logger.info(f"Fetched {len(all_newsletters)} newsletters for {self.name}")
        return all_newsletters

    def get_newsletter_urls(self) -> list[str]:
        """Get URLs of all newsletters in this category.

        Use Newsletter(url) to create Newsletter objects from these URLs.

        :returns: List of newsletter URLs.
        """
        data = self._fetch_newsletters_data()
        return [item["base_url"] for item in data]

    def get_newsletter_metadata(self) -> list[dict[str, Any]]:
        """Get full metadata for all newsletters in this category.

        :returns: List of newsletter metadata dictionaries.
        """
        return self._fetch_newsletters_data()

    def refresh_data(self) -> None:
        """Force refresh of the newsletter data cache."""
        logger.info(f"Refreshing data for {self.name}")
        self._fetch_newsletters_data(force_refresh=True)
