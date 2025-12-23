"""Tests for Notion database endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.notion.exceptions import NotionClientError


class TestGetDatabaseEndpoint(unittest.TestCase):
    """Tests for GET /notion/databases/{database_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_database_success(self, mock_client_class: MagicMock) -> None:
        """Test successful database retrieval."""
        mock_client = MagicMock()
        mock_client.get_database.return_value = {
            "id": "db-123",
            "title": [{"plain_text": "Tasks Database"}],
            "properties": {"Name": {"type": "title"}},
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/databases/db-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "db-123")
        self.assertEqual(data["title"], "Tasks Database")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_database_notion_error_returns_502(self, mock_client_class: MagicMock) -> None:
        """Test that Notion API errors return 502."""
        mock_client = MagicMock()
        mock_client.get_database.side_effect = NotionClientError("Database not found")
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/databases/invalid-db",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
