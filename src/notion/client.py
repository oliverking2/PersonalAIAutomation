"""Notion API client for interacting with databases, data sources, and pages."""

import logging
import os
from typing import Any

import requests

from src.notion.exceptions import NotionClientError

logger = logging.getLogger(__name__)

# Notion API timeout in seconds
REQUEST_TIMEOUT = 30

# Notion API version
NOTION_VERSION = "2025-09-03"


class NotionClient:
    """Client for interacting with the Notion API.

    Provides methods for querying databases, data sources, and managing pages.
    """

    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, *, token: str | None = None) -> None:
        """Initialise the Notion client.

        :param token: Notion integration token. If not provided, reads from
            NOTION_INTEGRATION_SECRET environment variable.
        :raises ValueError: If token is not provided and not found in environment.
        """
        self._token = token or os.environ.get("NOTION_INTEGRATION_SECRET")

        if not self._token:
            raise ValueError(
                "Notion integration token not provided. Set NOTION_INTEGRATION_SECRET "
                "environment variable or pass token parameter."
            )

        logger.debug("NotionClient initialised")

    @property
    def _headers(self) -> dict[str, str]:
        """Headers for Notion API requests.

        :returns: Dictionary of required headers.
        """
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def _get(self, endpoint: str) -> dict[str, Any]:
        """Make a GET request to the Notion API.

        :param endpoint: API endpoint path (without base URL).
        :returns: JSON response as dictionary.
        :raises NotionClientError: If the request fails.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"Making GET request to endpoint={endpoint}")

        try:
            response = requests.get(url, headers=self._headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            raise NotionClientError(f"Notion API request timed out after {REQUEST_TIMEOUT}s") from e
        except requests.exceptions.HTTPError as e:
            error_body = self._extract_error_message(e.response)
            raise NotionClientError(
                f"Notion API request failed: {e.response.status_code} - {error_body}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise NotionClientError(f"Notion API request failed: {e}") from e

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the Notion API.

        :param endpoint: API endpoint path (without base URL).
        :param payload: Request body as dictionary.
        :returns: JSON response as dictionary.
        :raises NotionClientError: If the request fails.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"Making POST request to endpoint={endpoint}")

        try:
            response = requests.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            raise NotionClientError(f"Notion API request timed out after {REQUEST_TIMEOUT}s") from e
        except requests.exceptions.HTTPError as e:
            error_body = self._extract_error_message(e.response)
            raise NotionClientError(
                f"Notion API request failed: {e.response.status_code} - {error_body}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise NotionClientError(f"Notion API request failed: {e}") from e

    def _patch(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a PATCH request to the Notion API.

        :param endpoint: API endpoint path (without base URL).
        :param payload: Request body as dictionary.
        :returns: JSON response as dictionary.
        :raises NotionClientError: If the request fails.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"Making PATCH request to endpoint={endpoint}")

        try:
            response = requests.patch(
                url,
                headers=self._headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            raise NotionClientError(f"Notion API request timed out after {REQUEST_TIMEOUT}s") from e
        except requests.exceptions.HTTPError as e:
            error_body = self._extract_error_message(e.response)
            raise NotionClientError(
                f"Notion API request failed: {e.response.status_code} - {error_body}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise NotionClientError(f"Notion API request failed: {e}") from e

    def _extract_error_message(self, response: requests.Response) -> str:
        """Extract error message from Notion API error response.

        :param response: Response object from failed request.
        :returns: Error message string.
        """
        try:
            data = response.json()
            return data.get("message", response.text)
        except ValueError:
            return response.text

    # Database endpoints

    def get_database(self, database_id: str) -> dict[str, Any]:
        """Retrieve database structure and properties.

        :param database_id: Notion database ID.
        :returns: Database object with properties schema.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Retrieving database: {database_id}")
        return self._get(f"databases/{database_id}")

    # Data source endpoints

    def get_data_source(self, data_source_id: str) -> dict[str, Any]:
        """Retrieve data source configuration.

        :param data_source_id: Notion data source ID.
        :returns: Data source object with configuration.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Retrieving data source: {data_source_id}")
        return self._get(f"data_sources/{data_source_id}")

    def query_data_source(
        self,
        data_source_id: str,
        *,
        filter_: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Query pages from a data source with filters.

        :param data_source_id: Notion data source ID.
        :param filter_: Optional filter object for the query.
        :param sorts: Optional list of sort objects.
        :param start_cursor: Cursor for pagination.
        :param page_size: Number of results per page (max 100).
        :returns: Query results with pages and pagination info.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Querying data source: {data_source_id}")
        payload: dict[str, Any] = {"page_size": min(page_size, 100)}

        if filter_ is not None:
            payload["filter"] = filter_

        if sorts is not None:
            payload["sorts"] = sorts

        if start_cursor is not None:
            payload["start_cursor"] = start_cursor

        return self._post(f"data_sources/{data_source_id}/query", payload)

    def query_all_data_source(
        self,
        data_source_id: str,
        *,
        filter_: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Query all pages from a data source, handling pagination automatically.

        :param data_source_id: Notion data source ID.
        :param filter_: Optional filter object for the query.
        :param sorts: Optional list of sort objects.
        :returns: List of all pages matching the query.
        :raises NotionClientError: If any request fails.
        """
        logger.info(f"Querying all pages from data source: {data_source_id}")
        all_results: list[dict[str, Any]] = []
        start_cursor: str | None = None

        while True:
            response = self.query_data_source(
                data_source_id,
                filter_=filter_,
                sorts=sorts,
                start_cursor=start_cursor,
                page_size=100,
            )

            all_results.extend(response.get("results", []))

            if not response.get("has_more", False):
                break

            start_cursor = response.get("next_cursor")
            if start_cursor is None:
                break

        logger.info(f"Retrieved {len(all_results)} pages from data source: {data_source_id}")
        return all_results

    def list_data_source_templates(self) -> dict[str, Any]:
        """List available data source templates.

        :returns: List of template objects.
        :raises NotionClientError: If the request fails.
        """
        logger.info("Listing data source templates")
        return self._get("data_sources/templates")

    # Page endpoints

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Retrieve a single page.

        :param page_id: Notion page ID.
        :returns: Page object with properties.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Retrieving page: {page_id}")
        return self._get(f"pages/{page_id}")

    def create_page(
        self,
        data_source_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new page in a data source.

        :param data_source_id: Parent data source ID.
        :param properties: Page properties to set.
        :returns: Created page object.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Creating page in data source: {data_source_id}")
        payload = {
            "parent": {"data_source_id": data_source_id},
            "properties": properties,
        }
        return self._post("pages", payload)

    def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a page's properties.

        :param page_id: Notion page ID.
        :param properties: Properties to update.
        :returns: Updated page object.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Updating page: {page_id}")
        payload = {"properties": properties}
        return self._patch(f"pages/{page_id}", payload)

    # Block (page content) endpoints

    def get_page_content(self, page_id: str) -> list[dict[str, Any]]:
        """Get all blocks from a page.

        Retrieves the page's child blocks, handling pagination automatically.

        :param page_id: The Notion page ID.
        :returns: List of block objects.
        :raises NotionClientError: If the request fails.
        """
        logger.info(f"Retrieving page content: {page_id}")
        all_blocks: list[dict[str, Any]] = []
        start_cursor: str | None = None

        while True:
            endpoint = f"blocks/{page_id}/children"
            if start_cursor:
                endpoint = f"{endpoint}?start_cursor={start_cursor}"

            response = self._get(endpoint)
            all_blocks.extend(response.get("results", []))

            if not response.get("has_more", False):
                break

            start_cursor = response.get("next_cursor")
            if start_cursor is None:
                break

        logger.info(f"Retrieved {len(all_blocks)} blocks from page: {page_id}")
        return all_blocks

    def append_page_content(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
        """Append blocks to a page.

        :param page_id: The Notion page ID.
        :param blocks: List of block objects to append.
        :raises NotionClientError: If the request fails.
        """
        if not blocks:
            logger.debug(f"No blocks to append to page: {page_id}")
            return

        logger.info(f"Appending {len(blocks)} blocks to page: {page_id}")
        payload = {"children": blocks}
        self._patch(f"blocks/{page_id}/children", payload)

    def _delete_block(self, block_id: str) -> None:
        """Delete a block.

        :param block_id: The block ID to delete.
        :raises NotionClientError: If the request fails.
        """
        logger.debug(f"Deleting block: {block_id}")
        url = f"{self.BASE_URL}/blocks/{block_id}"

        try:
            response = requests.delete(url, headers=self._headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

        except requests.exceptions.Timeout as e:
            raise NotionClientError(f"Notion API request timed out after {REQUEST_TIMEOUT}s") from e
        except requests.exceptions.HTTPError as e:
            error_body = self._extract_error_message(e.response)
            raise NotionClientError(
                f"Notion API request failed: {e.response.status_code} - {error_body}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise NotionClientError(f"Notion API request failed: {e}") from e

    def replace_page_content(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
        """Replace all page content with new blocks.

        Deletes all existing blocks and appends the new ones.

        :param page_id: The Notion page ID.
        :param blocks: List of block objects to set as the new content.
        :raises NotionClientError: If any request fails.
        """
        logger.info(f"Replacing content for page: {page_id}")

        # Get existing blocks and delete them
        existing_blocks = self.get_page_content(page_id)
        for block in existing_blocks:
            block_id = block.get("id")
            if block_id:
                self._delete_block(block_id)

        # Append new blocks
        self.append_page_content(page_id, blocks)
