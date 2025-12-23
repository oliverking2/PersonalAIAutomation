"""Tests for Notion data source endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app


class TestGetDataSourceEndpoint(unittest.TestCase):
    """Tests for GET /notion/data-sources/{data_source_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_data_source_success(self, mock_client_class: MagicMock) -> None:
        """Test successful data source retrieval."""
        mock_client = MagicMock()
        mock_client.get_data_source.return_value = {
            "id": "ds-123",
            "database_id": "db-456",
            "properties": {"Status": {"type": "status"}},
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/data-sources/ds-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "ds-123")
        self.assertEqual(data["database_id"], "db-456")


class TestQueryDataSourceEndpoint(unittest.TestCase):
    """Tests for POST /notion/data-sources/{data_source_id}/query endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_data_source_success(self, mock_client_class: MagicMock) -> None:
        """Test successful data source query with automatic pagination."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "page-1",
                "url": "https://notion.so/Task-1",
                "properties": {
                    "Task name": {"title": [{"plain_text": "Task 1"}]},
                    "Status": {"status": {"name": "Not started"}},
                    "Due date": {"date": {"start": "2025-12-25"}},
                    "Priority": {"select": {"name": "High"}},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/data-sources/ds-123/query",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["task_name"], "Task 1")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_data_source_with_filter(self, mock_client_class: MagicMock) -> None:
        """Test data source query with filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        filter_obj = {"property": "Status", "status": {"equals": "Done"}}
        response = self.client.post(
            "/notion/data-sources/ds-123/query",
            headers=self.auth_headers,
            json={"filter": filter_obj},
        )

        self.assertEqual(response.status_code, 200)
        mock_client.query_all_data_source.assert_called_once()
        call_kwargs = mock_client.query_all_data_source.call_args.kwargs
        self.assertEqual(call_kwargs["filter_"], filter_obj)


class TestListTemplatesEndpoint(unittest.TestCase):
    """Tests for GET /notion/data-sources/templates endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_list_templates_success(self, mock_client_class: MagicMock) -> None:
        """Test successful template listing."""
        mock_client = MagicMock()
        mock_client.list_data_source_templates.return_value = {
            "results": [{"id": "template-1", "name": "Tasks"}]
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/data-sources/templates",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["templates"]), 1)


if __name__ == "__main__":
    unittest.main()
