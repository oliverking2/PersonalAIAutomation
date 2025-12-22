"""Tests for Notion API endpoints."""

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


class TestNotionEndpointsAuthentication(unittest.TestCase):
    """Tests for Notion endpoint authentication."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_get_database_without_auth_returns_401(self) -> None:
        """Test that requests without auth token are rejected."""
        response = self.client.get("/notion/databases/db-123")
        # HTTPBearer returns 401 when credentials are missing
        self.assertEqual(response.status_code, 401)

    def test_get_database_with_invalid_auth_returns_401(self) -> None:
        """Test that requests with invalid auth token are rejected."""
        response = self.client.get(
            "/notion/databases/db-123",
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertEqual(response.status_code, 401)


class TestGetDatabaseEndpoint(unittest.TestCase):
    """Tests for GET /notion/databases/{database_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.endpoints.NotionClient")
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

    @patch("src.api.notion.endpoints.NotionClient")
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


class TestGetDataSourceEndpoint(unittest.TestCase):
    """Tests for GET /notion/data-sources/{data_source_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.endpoints.NotionClient")
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

    @patch("src.api.notion.endpoints.NotionClient")
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

    @patch("src.api.notion.endpoints.NotionClient")
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

    @patch("src.api.notion.endpoints.NotionClient")
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


class TestGetPageEndpoint(unittest.TestCase):
    """Tests for GET /notion/pages/{page_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.endpoints.NotionClient")
    def test_get_page_success(self, mock_client_class: MagicMock) -> None:
        """Test successful page retrieval."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = {
            "id": "page-123",
            "url": "https://notion.so/My-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "My Task"}]},
                "Status": {"status": {"name": "In progress"}},
                "Due date": {"date": {"start": "2025-12-25"}},
                "Priority": {"select": {"name": "High"}},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/pages/page-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "page-123")
        self.assertEqual(data["task_name"], "My Task")
        self.assertEqual(data["status"], "In progress")


class TestCreatePageEndpoint(unittest.TestCase):
    """Tests for POST /notion/pages endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.endpoints.NotionClient")
    def test_create_page_success(self, mock_client_class: MagicMock) -> None:
        """Test successful page creation."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "page-new",
            "url": "https://notion.so/New-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "New Task"}]},
                "Status": {"status": {"name": "Not started"}},
                "Due date": {"date": {"start": "2025-12-31"}},
                "Priority": {"select": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/pages",
            headers=self.auth_headers,
            json={
                "data_source_id": "ds-123",
                "task_name": "New Task",
                "status": "Not started",
                "due_date": "2025-12-31",
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "page-new")
        self.assertEqual(data["task_name"], "New Task")

    @patch("src.api.notion.endpoints.NotionClient")
    def test_create_page_minimal(self, mock_client_class: MagicMock) -> None:
        """Test page creation with minimal fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "page-min",
            "url": "https://notion.so/Minimal",
            "properties": {
                "Task name": {"title": [{"plain_text": "Minimal"}]},
                "Status": {"status": None},
                "Due date": {"date": None},
                "Priority": {"select": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/pages",
            headers=self.auth_headers,
            json={
                "data_source_id": "ds-123",
                "task_name": "Minimal",
            },
        )

        self.assertEqual(response.status_code, 201)

    def test_create_page_missing_required_field_returns_422(self) -> None:
        """Test that missing required field returns 422."""
        response = self.client.post(
            "/notion/pages",
            headers=self.auth_headers,
            json={
                "data_source_id": "ds-123",
                # missing task_name
            },
        )

        self.assertEqual(response.status_code, 422)


class TestUpdatePageEndpoint(unittest.TestCase):
    """Tests for PATCH /notion/pages/{page_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.endpoints.NotionClient")
    def test_update_page_success(self, mock_client_class: MagicMock) -> None:
        """Test successful page update."""
        mock_client = MagicMock()
        mock_client.update_page.return_value = {
            "id": "page-123",
            "url": "https://notion.so/Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "Task"}]},
                "Status": {"status": {"name": "Complete"}},
                "Due date": {"date": None},
                "Priority": {"select": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/pages/page-123",
            headers=self.auth_headers,
            json={"status": "Complete"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "Complete")

    @patch("src.api.notion.endpoints.NotionClient")
    def test_update_page_no_fields_returns_400(self, mock_client_class: MagicMock) -> None:
        """Test that update with no fields returns 400."""
        mock_client_class.return_value = MagicMock()

        response = self.client.patch(
            "/notion/pages/page-123",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No properties to update", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
