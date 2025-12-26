"""Tests for Notion task endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_TASK_DATA_SOURCE_ID", "test-data-source-id")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app


class TestQueryTasksEndpoint(unittest.TestCase):
    """Tests for POST /notion/tasks/query endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_tasks_success(self, mock_client_class: MagicMock) -> None:
        """Test successful task query."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "task-1",
                "url": "https://notion.so/Task-1",
                "properties": {
                    "Task name": {"title": [{"plain_text": "Task 1"}]},
                    "Status": {"status": {"name": "Not started"}},
                    "Due date": {"date": {"start": "2025-12-25"}},
                    "Priority": {"select": {"name": "High"}},
                    "Effort level": {"select": {"name": "Medium"}},
                    "Task Group": {"select": {"name": "Work"}},
                    "Description": {"rich_text": [{"plain_text": "A description"}]},
                    "Assignee": {"people": [{"name": "John"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks/query",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        task = data["results"][0]
        self.assertEqual(task["task_name"], "Task 1")
        self.assertEqual(task["priority"], "High")
        self.assertEqual(task["effort_level"], "Medium")
        self.assertEqual(task["task_group"], "Work")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_tasks_with_filter(self, mock_client_class: MagicMock) -> None:
        """Test task query with filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        filter_obj = {"property": "Status", "status": {"does_not_equal": "Done"}}
        response = self.client.post(
            "/notion/tasks/query",
            headers=self.auth_headers,
            json={"filter": filter_obj},
        )

        self.assertEqual(response.status_code, 200)
        mock_client.query_all_data_source.assert_called_once()


class TestGetTaskEndpoint(unittest.TestCase):
    """Tests for GET /notion/tasks/{task_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_task_success(self, mock_client_class: MagicMock) -> None:
        """Test successful task retrieval."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = {
            "id": "task-123",
            "url": "https://notion.so/My-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "My Task"}]},
                "Status": {"status": {"name": "In progress"}},
                "Due date": {"date": {"start": "2025-12-25"}},
                "Priority": {"select": {"name": "High"}},
                "Effort level": {"select": {"name": "Small"}},
                "Task Group": {"select": {"name": "Personal"}},
                "Description": {"rich_text": []},
                "Assignee": {"people": []},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "task-123")
        self.assertEqual(data["task_name"], "My Task")
        self.assertEqual(data["effort_level"], "Small")


class TestCreateTaskEndpoint(unittest.TestCase):
    """Tests for POST /notion/tasks endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_task_success(self, mock_client_class: MagicMock) -> None:
        """Test successful task creation with all fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "task-new",
            "url": "https://notion.so/New-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "New Task"}]},
                "Status": {"status": {"name": "Not started"}},
                "Due date": {"date": {"start": "2025-12-31"}},
                "Priority": {"select": {"name": "High"}},
                "Effort level": {"select": {"name": "Large"}},
                "Task Group": {"select": {"name": "Work"}},
                "Assignee": {"people": []},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={
                "task_name": "New Task",
                "status": "Not started",
                "due_date": "2025-12-31",
                "priority": "High",
                "effort_level": "Large",
                "task_group": "Work",
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "task-new")
        self.assertEqual(data["task_name"], "New Task")
        self.assertEqual(data["priority"], "High")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_task_minimal(self, mock_client_class: MagicMock) -> None:
        """Test task creation with minimal fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "task-min",
            "url": "https://notion.so/Minimal",
            "properties": {
                "Task name": {"title": [{"plain_text": "Minimal"}]},
                "Status": {"status": None},
                "Due date": {"date": None},
                "Priority": {"select": None},
                "Effort level": {"select": None},
                "Task Group": {"select": None},
                "Description": {"rich_text": []},
                "Assignee": {"people": []},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={
                "task_name": "Minimal",
                "due_date": "2025-06-01",
                "task_group": "Personal",
            },
        )

        self.assertEqual(response.status_code, 201)

    def test_create_task_missing_name_returns_422(self) -> None:
        """Test that missing task_name returns 422 with readable error."""
        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={"status": "Not started"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("task_name", detail)
        self.assertIn("field required", detail)

    def test_create_task_invalid_status_returns_422(self) -> None:
        """Test that invalid status enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={"task_name": "Task", "status": "Invalid"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("status", detail)
        self.assertIn("invalid value 'Invalid'", detail)
        self.assertIn("Expected:", detail)

    def test_create_task_invalid_priority_returns_422(self) -> None:
        """Test that invalid priority enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={"task_name": "Task", "priority": "Critical"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("priority", detail)
        self.assertIn("invalid value 'Critical'", detail)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_task_duplicate_name_returns_409(self, mock_client_class: MagicMock) -> None:
        """Test that duplicate task name returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "existing-task",
                "properties": {
                    "Task name": {"title": [{"plain_text": "Existing Task"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={
                "task_name": "existing task",  # case insensitive match
                "due_date": "2025-06-01",
                "task_group": "Work",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_task_no_duplicate_succeeds(self, mock_client_class: MagicMock) -> None:
        """Test that non-duplicate task name succeeds."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "existing-task",
                "properties": {
                    "Task name": {"title": [{"plain_text": "Other Task"}]},
                },
            }
        ]
        mock_client.create_page.return_value = {
            "id": "new-task",
            "url": "https://notion.so/New-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "New Task"}]},
                "Status": {"status": {"name": "Not started"}},
                "Due date": {"date": None},
                "Priority": {"select": None},
                "Effort level": {"select": None},
                "Task Group": {"select": None},
                "Assignee": {"people": []},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json={
                "task_name": "New Task",
                "due_date": "2025-06-01",
                "task_group": "Work",
            },
        )

        self.assertEqual(response.status_code, 201)


class TestUpdateTaskEndpoint(unittest.TestCase):
    """Tests for PATCH /notion/tasks/{task_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_task_success(self, mock_client_class: MagicMock) -> None:
        """Test successful task update."""
        mock_client = MagicMock()
        mock_client.update_page.return_value = {
            "id": "task-123",
            "url": "https://notion.so/Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "Task"}]},
                "Status": {"status": {"name": "Done"}},
                "Due date": {"date": None},
                "Priority": {"select": {"name": "Low"}},
                "Effort level": {"select": None},
                "Task Group": {"select": None},
                "Description": {"rich_text": []},
                "Assignee": {"people": []},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
            json={"status": "Done", "priority": "Low"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "Done")
        self.assertEqual(data["priority"], "Low")

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_task_no_fields_returns_400(self, mock_client_class: MagicMock) -> None:
        """Test that update with no fields returns 400."""
        mock_client_class.return_value = MagicMock()

        response = self.client.patch(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No properties or content to update", response.json()["detail"])

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_task_duplicate_name_returns_409(self, mock_client_class: MagicMock) -> None:
        """Test that updating to duplicate task name returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "other-task",
                "properties": {
                    "Task name": {"title": [{"plain_text": "Other Task"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
            json={"task_name": "OTHER TASK"},  # case insensitive match
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_task_same_name_excludes_self(self, mock_client_class: MagicMock) -> None:
        """Test that updating to same name excludes current task from check."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "task-123",  # Same ID as the task being updated
                "properties": {
                    "Task name": {"title": [{"plain_text": "My Task"}]},
                },
            }
        ]
        mock_client.update_page.return_value = {
            "id": "task-123",
            "url": "https://notion.so/Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "My Task"}]},
                "Status": {"status": {"name": "Done"}},
                "Due date": {"date": None},
                "Priority": {"select": None},
                "Effort level": {"select": None},
                "Task Group": {"select": None},
                "Assignee": {"people": []},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
            json={"task_name": "My Task"},
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
