"""Tests for Notion task endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_TASK_DATA_SOURCE_ID", "test-data-source-id")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from testing.api.notion.fixtures import (
    DEFAULT_EFFORT,
    DEFAULT_PRIORITY,
    DEFAULT_TASK_GROUP,
    DEFAULT_TASK_STATUS,
    build_notion_task_page,
    build_task_create_payload,
)


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
            build_notion_task_page(
                page_id="task-1",
                url="https://notion.so/Task-1",
                task_name="Task 1",
                description="A description",
            )
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
        # Verify enum fields are present (values come from fixtures)
        self.assertEqual(task["priority"], DEFAULT_PRIORITY)
        self.assertEqual(task["effort_level"], DEFAULT_EFFORT)
        self.assertEqual(task["task_group"], DEFAULT_TASK_GROUP)

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
        mock_client.get_page.return_value = build_notion_task_page(
            page_id="task-123",
            url="https://notion.so/My-Task",
            task_name="My Task",
        )
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "task-123")
        self.assertEqual(data["task_name"], "My Task")
        self.assertEqual(data["effort_level"], DEFAULT_EFFORT)


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
        mock_client.create_page.return_value = build_notion_task_page(
            page_id="task-new",
            url="https://notion.so/New-Task",
            task_name="New Task",
        )
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json=[
                build_task_create_payload(
                    task_name="New Task",
                    status=DEFAULT_TASK_STATUS,
                    priority=DEFAULT_PRIORITY,
                    effort_level=DEFAULT_EFFORT,
                )
            ],
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data["created"]), 1)
        self.assertEqual(len(data["failed"]), 0)
        self.assertEqual(data["created"][0]["id"], "task-new")
        self.assertEqual(data["created"][0]["task_name"], "New Task")
        self.assertEqual(data["created"][0]["priority"], DEFAULT_PRIORITY)

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
            json=[build_task_create_payload(task_name="Minimal")],
        )

        self.assertEqual(response.status_code, 201)

    def test_create_task_missing_name_returns_422(self) -> None:
        """Test that missing task_name returns 422 with readable error."""
        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json=[{"status": DEFAULT_TASK_STATUS}],
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
            json=[{"task_name": "Task", "status": "InvalidStatus"}],
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("status", detail)
        self.assertIn("invalid value 'InvalidStatus'", detail)
        self.assertIn("Expected:", detail)

    def test_create_task_invalid_priority_returns_422(self) -> None:
        """Test that invalid priority enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json=[{"task_name": "Task", "priority": "InvalidPriority"}],
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("priority", detail)
        self.assertIn("invalid value 'InvalidPriority'", detail)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_task_duplicate_name_returns_failure(self, mock_client_class: MagicMock) -> None:
        """Test that duplicate task name is reported in failures."""
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
            json=[build_task_create_payload(task_name="existing task")],
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data["created"]), 0)
        self.assertEqual(len(data["failed"]), 1)
        self.assertEqual(data["failed"][0]["name"], "existing task")
        self.assertIn("already exists", data["failed"][0]["error"])

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
        mock_client.create_page.return_value = build_notion_task_page(
            page_id="new-task",
            url="https://notion.so/New-Task",
            task_name="New Task",
        )
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/tasks",
            headers=self.auth_headers,
            json=[build_task_create_payload(task_name="New Task")],
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data["created"]), 1)
        self.assertEqual(len(data["failed"]), 0)


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
        mock_client.update_page.return_value = build_notion_task_page(
            page_id="task-123",
            url="https://notion.so/Task",
            task_name="Task",
        )
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
            json={"status": DEFAULT_TASK_STATUS, "priority": DEFAULT_PRIORITY},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], DEFAULT_TASK_STATUS)
        self.assertEqual(data["priority"], DEFAULT_PRIORITY)

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
        mock_client.update_page.return_value = build_notion_task_page(
            page_id="task-123",
            url="https://notion.so/Task",
            task_name="My Task",
        )
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/tasks/task-123",
            headers=self.auth_headers,
            json={"task_name": "My Task"},
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
