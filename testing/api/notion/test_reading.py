"""Tests for Notion reading list endpoints."""

import os

# Set required environment variables before importing API modules

os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_READING_LIST_DATA_SOURCE_ID", "test-reading-data-source-id")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from testing.api.notion.fixtures import (
    DEFAULT_PRIORITY,
    DEFAULT_READING_CATEGORY,
    DEFAULT_READING_STATUS,
    DEFAULT_READING_TYPE,
    build_notion_reading_page,
    build_reading_create_payload,
)


class TestQueryReadingEndpoint(unittest.TestCase):
    """Tests for POST /notion/reading-list/query endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_reading_success(self, mock_client_class: MagicMock) -> None:
        """Test successful reading list query."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            build_notion_reading_page(
                page_id="reading-1",
                url="https://notion.so/Reading-1",
                title="Clean Code",
                item_url="https://example.com/book",
            )
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading-list/query",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        item = data["results"][0]
        self.assertEqual(item["title"], "Clean Code")
        self.assertEqual(item["item_type"], DEFAULT_READING_TYPE)
        self.assertEqual(item["status"], DEFAULT_READING_STATUS)
        self.assertEqual(item["priority"], DEFAULT_PRIORITY)
        self.assertEqual(item["category"], DEFAULT_READING_CATEGORY)
        self.assertEqual(item["item_url"], "https://example.com/book")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_reading_with_status_filter(self, mock_client_class: MagicMock) -> None:
        """Test reading list query with status filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading-list/query",
            headers=self.auth_headers,
            json={"status": DEFAULT_READING_STATUS},
        )

        self.assertEqual(response.status_code, 200)
        # Verify the filter was built correctly (includes exclude Completed + status filter)
        call_args = mock_client.query_all_data_source.call_args
        filter_arg = call_args[1]["filter_"]
        self.assertIn("and", filter_arg)
        conditions = filter_arg["and"]
        # Should have exclude Completed + status equals filter
        status_conditions = [c for c in conditions if c.get("property") == "Status"]
        self.assertEqual(len(status_conditions), 2)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_reading_with_multiple_filters(self, mock_client_class: MagicMock) -> None:
        """Test reading list query with multiple filters."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading-list/query",
            headers=self.auth_headers,
            json={
                "status": DEFAULT_READING_STATUS,
                "category": DEFAULT_READING_CATEGORY,
                "priority": DEFAULT_PRIORITY,
            },
        )

        self.assertEqual(response.status_code, 200)
        # Verify the combined filter was built correctly
        # (includes exclude Completed + status + category + priority)
        call_args = mock_client.query_all_data_source.call_args
        filter_arg = call_args[1]["filter_"]
        self.assertIn("and", filter_arg)
        self.assertEqual(len(filter_arg["and"]), 4)


class TestGetReadingItemEndpoint(unittest.TestCase):
    """Tests for GET /notion/reading-list/{item_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_reading_item_success(self, mock_client_class: MagicMock) -> None:
        """Test successful reading item retrieval."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = build_notion_reading_page(
            page_id="reading-123",
            url="https://notion.so/My-Book",
            title="My Book",
            item_url=None,
        )
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/reading-list/reading-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "reading-123")
        self.assertEqual(data["title"], "My Book")
        self.assertEqual(data["item_type"], DEFAULT_READING_TYPE)
        self.assertEqual(data["category"], DEFAULT_READING_CATEGORY)


class TestCreateReadingItemEndpoint(unittest.TestCase):
    """Tests for POST /notion/reading-list endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_reading_item_success(self, mock_client_class: MagicMock) -> None:
        """Test successful reading item creation with all fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = build_notion_reading_page(
            page_id="reading-new",
            url="https://notion.so/New-Article",
            title="New Article",
            item_url="https://example.com/article",
        )
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json=build_reading_create_payload(
                title="New Article",
                status=DEFAULT_READING_STATUS,
                priority=DEFAULT_PRIORITY,
                category=DEFAULT_READING_CATEGORY,
                item_url="https://example.com/article",
            ),
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "reading-new")
        self.assertEqual(data["title"], "New Article")
        self.assertEqual(data["item_type"], DEFAULT_READING_TYPE)
        self.assertEqual(data["priority"], DEFAULT_PRIORITY)
        self.assertEqual(data["category"], DEFAULT_READING_CATEGORY)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_reading_item_minimal(self, mock_client_class: MagicMock) -> None:
        """Test reading item creation with minimal fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "reading-min",
            "url": "https://notion.so/Minimal",
            "properties": {
                "Title": {"title": [{"plain_text": "Minimal"}]},
                "Type": {"select": {"name": DEFAULT_READING_TYPE}},
                "Status": {"status": {"name": DEFAULT_READING_STATUS}},
                "Priority": {"select": None},
                "Category": {"select": None},
                "URL": {"url": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json=build_reading_create_payload(title="Minimal"),
        )

        self.assertEqual(response.status_code, 201)

    def test_create_reading_item_missing_title_returns_422(self) -> None:
        """Test that missing title returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json={"item_type": DEFAULT_READING_TYPE},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("title", detail)
        self.assertIn("field required", detail)

    def test_create_reading_item_missing_type_returns_422(self) -> None:
        """Test that missing item_type returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json={"title": "Article"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("item_type", detail)
        self.assertIn("field required", detail)

    def test_create_reading_item_invalid_status_returns_422(self) -> None:
        """Test that invalid status enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json={"title": "Article", "item_type": DEFAULT_READING_TYPE, "status": "Invalid"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("status", detail)
        self.assertIn("invalid value 'Invalid'", detail)

    def test_create_reading_item_invalid_category_returns_422(self) -> None:
        """Test that invalid category enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json={
                "title": "Article",
                "item_type": DEFAULT_READING_TYPE,
                "category": "Invalid Category",
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("category", detail)
        self.assertIn("invalid value 'Invalid Category'", detail)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_reading_item_duplicate_title_returns_409(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test that duplicate title returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "existing-item",
                "properties": {
                    "Title": {"title": [{"plain_text": "Existing Article"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading-list",
            headers=self.auth_headers,
            json=build_reading_create_payload(title="existing article"),
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])


class TestUpdateReadingItemEndpoint(unittest.TestCase):
    """Tests for PATCH /notion/reading-list/{item_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_reading_item_success(self, mock_client_class: MagicMock) -> None:
        """Test successful reading item update."""
        mock_client = MagicMock()
        mock_client.update_page.return_value = build_notion_reading_page(
            page_id="reading-123",
            url="https://notion.so/Article",
            title="Article",
            category=None,
            item_url=None,
        )
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/reading-list/reading-123",
            headers=self.auth_headers,
            json={"status": DEFAULT_READING_STATUS, "item_type": DEFAULT_READING_TYPE},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], DEFAULT_READING_STATUS)
        self.assertEqual(data["item_type"], DEFAULT_READING_TYPE)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_reading_item_no_fields_returns_400(self, mock_client_class: MagicMock) -> None:
        """Test that update with no fields returns 400."""
        mock_client_class.return_value = MagicMock()

        response = self.client.patch(
            "/notion/reading-list/reading-123",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No properties or content to update", response.json()["detail"])

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_reading_item_duplicate_title_returns_409(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test that updating to duplicate title returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "other-item",
                "properties": {
                    "Title": {"title": [{"plain_text": "Other Article"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/reading-list/reading-123",
            headers=self.auth_headers,
            json={"title": "OTHER ARTICLE"},  # case insensitive match
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
