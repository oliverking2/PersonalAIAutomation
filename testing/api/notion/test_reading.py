"""Tests for Notion reading list endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_READING_LIST_DATA_SOURCE_ID", "test-reading-data-source-id")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app


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
            {
                "id": "reading-1",
                "url": "https://notion.so/Reading-1",
                "properties": {
                    "Title": {"title": [{"plain_text": "Clean Code"}]},
                    "Status": {"status": {"name": "Reading Now"}},
                    "Priority": {"select": {"name": "High"}},
                    "Category": {"select": {"name": "Data Engineering"}},
                    "URL": {"url": "https://example.com/book"},
                    "Read Date": {"date": None},
                },
            }
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
        self.assertEqual(item["status"], "Reading Now")
        self.assertEqual(item["priority"], "High")
        self.assertEqual(item["category"], "Data Engineering")
        self.assertEqual(item["item_url"], "https://example.com/book")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_reading_with_filter(self, mock_client_class: MagicMock) -> None:
        """Test reading list query with filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        filter_obj = {"property": "Status", "status": {"equals": "To Read"}}
        response = self.client.post(
            "/notion/reading-list/query",
            headers=self.auth_headers,
            json={"filter": filter_obj},
        )

        self.assertEqual(response.status_code, 200)
        mock_client.query_all_data_source.assert_called_once()


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
        mock_client.get_page.return_value = {
            "id": "reading-123",
            "url": "https://notion.so/My-Book",
            "properties": {
                "Title": {"title": [{"plain_text": "My Book"}]},
                "Status": {"status": {"name": "Completed"}},
                "Priority": {"select": {"name": "Medium"}},
                "Category": {"select": {"name": "AI"}},
                "URL": {"url": None},
                "Read Date": {"date": {"start": "2025-12-20"}},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/reading-list/reading-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "reading-123")
        self.assertEqual(data["title"], "My Book")
        self.assertEqual(data["category"], "AI")
        self.assertEqual(data["read_date"], "2025-12-20")


class TestCreateReadingItemEndpoint(unittest.TestCase):
    """Tests for POST /notion/reading endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_reading_item_success(self, mock_client_class: MagicMock) -> None:
        """Test successful reading item creation with all fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "reading-new",
            "url": "https://notion.so/New-Article",
            "properties": {
                "Title": {"title": [{"plain_text": "New Article"}]},
                "Status": {"status": {"name": "To Read"}},
                "Priority": {"select": {"name": "High"}},
                "Category": {"select": {"name": "Data Science"}},
                "URL": {"url": "https://example.com/article"},
                "Read Date": {"date": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading",
            headers=self.auth_headers,
            json={
                "title": "New Article",
                "status": "To Read",
                "priority": "High",
                "category": "Data Science",
                "item_url": "https://example.com/article",
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "reading-new")
        self.assertEqual(data["title"], "New Article")
        self.assertEqual(data["priority"], "High")
        self.assertEqual(data["category"], "Data Science")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_reading_item_minimal(self, mock_client_class: MagicMock) -> None:
        """Test reading item creation with minimal fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "reading-min",
            "url": "https://notion.so/Minimal",
            "properties": {
                "Title": {"title": [{"plain_text": "Minimal"}]},
                "Status": {"status": {"name": "To Read"}},
                "Priority": {"select": None},
                "Category": {"select": None},
                "URL": {"url": None},
                "Read Date": {"date": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/reading",
            headers=self.auth_headers,
            json={"title": "Minimal"},
        )

        self.assertEqual(response.status_code, 201)

    def test_create_reading_item_missing_title_returns_422(self) -> None:
        """Test that missing title returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading",
            headers=self.auth_headers,
            json={"status": "To Read"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("title", detail)
        self.assertIn("field required", detail)

    def test_create_reading_item_invalid_status_returns_422(self) -> None:
        """Test that invalid status enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading",
            headers=self.auth_headers,
            json={"title": "Article", "status": "Invalid"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("status", detail)
        self.assertIn("invalid value 'Invalid'", detail)

    def test_create_reading_item_invalid_category_returns_422(self) -> None:
        """Test that invalid category enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/reading",
            headers=self.auth_headers,
            json={"title": "Article", "category": "Invalid Category"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("category", detail)
        self.assertIn("invalid value 'Invalid Category'", detail)


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
        mock_client.update_page.return_value = {
            "id": "reading-123",
            "url": "https://notion.so/Article",
            "properties": {
                "Title": {"title": [{"plain_text": "Article"}]},
                "Status": {"status": {"name": "Completed"}},
                "Priority": {"select": {"name": "Low"}},
                "Category": {"select": None},
                "URL": {"url": None},
                "Read Date": {"date": {"start": "2025-12-24"}},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/reading-list/reading-123",
            headers=self.auth_headers,
            json={"status": "Completed", "read_date": "2025-12-24"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "Completed")
        self.assertEqual(data["read_date"], "2025-12-24")

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
        self.assertIn("No properties to update", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
