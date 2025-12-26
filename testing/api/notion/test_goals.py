"""Tests for Notion goals endpoints."""

import os

# Set required environment variables before importing API modules

os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_GOALS_DATA_SOURCE_ID", "test-goals-data-source-id")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app


class TestQueryGoalsEndpoint(unittest.TestCase):
    """Tests for POST /notion/goals/query endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_goals_success(self, mock_client_class: MagicMock) -> None:
        """Test successful goals query."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "goal-1",
                "url": "https://notion.so/Goal-1",
                "properties": {
                    "Goal name": {"title": [{"plain_text": "Learn Python"}]},
                    "Status": {"status": {"name": "In progress"}},
                    "Priority": {"select": {"name": "High"}},
                    "Progress": {"number": 50},
                    "Due date": {"date": {"start": "2025-12-31"}},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/goals/query",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        goal = data["results"][0]
        self.assertEqual(goal["goal_name"], "Learn Python")
        self.assertEqual(goal["status"], "In progress")
        self.assertEqual(goal["priority"], "High")
        self.assertEqual(goal["progress"], 50)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_goals_with_filter(self, mock_client_class: MagicMock) -> None:
        """Test goals query with filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        filter_obj = {"property": "Status", "status": {"does_not_equal": "Done"}}
        response = self.client.post(
            "/notion/goals/query",
            headers=self.auth_headers,
            json={"filter": filter_obj},
        )

        self.assertEqual(response.status_code, 200)
        mock_client.query_all_data_source.assert_called_once()


class TestGetGoalEndpoint(unittest.TestCase):
    """Tests for GET /notion/goals/{goal_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_goal_success(self, mock_client_class: MagicMock) -> None:
        """Test successful goal retrieval."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = {
            "id": "goal-123",
            "url": "https://notion.so/My-Goal",
            "properties": {
                "Goal name": {"title": [{"plain_text": "My Goal"}]},
                "Status": {"status": {"name": "Not started"}},
                "Priority": {"select": {"name": "Medium"}},
                "Progress": {"number": 0},
                "Due date": {"date": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/goals/goal-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "goal-123")
        self.assertEqual(data["goal_name"], "My Goal")
        self.assertEqual(data["progress"], 0)


class TestCreateGoalEndpoint(unittest.TestCase):
    """Tests for POST /notion/goals endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_goal_success(self, mock_client_class: MagicMock) -> None:
        """Test successful goal creation with all fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "goal-new",
            "url": "https://notion.so/New-Goal",
            "properties": {
                "Goal name": {"title": [{"plain_text": "New Goal"}]},
                "Status": {"status": {"name": "Not started"}},
                "Priority": {"select": {"name": "High"}},
                "Progress": {"number": 25},
                "Due date": {"date": {"start": "2025-12-31"}},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/goals",
            headers=self.auth_headers,
            json={
                "goal_name": "New Goal",
                "status": "Not started",
                "priority": "High",
                "progress": 25,
                "due_date": "2025-12-31",
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "goal-new")
        self.assertEqual(data["goal_name"], "New Goal")
        self.assertEqual(data["priority"], "High")
        self.assertEqual(data["progress"], 25)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_goal_minimal(self, mock_client_class: MagicMock) -> None:
        """Test goal creation with minimal fields."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {
            "id": "goal-min",
            "url": "https://notion.so/Minimal",
            "properties": {
                "Goal name": {"title": [{"plain_text": "Minimal"}]},
                "Status": {"status": {"name": "Not started"}},
                "Priority": {"select": None},
                "Progress": {"number": None},
                "Due date": {"date": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/goals",
            headers=self.auth_headers,
            json={"goal_name": "Minimal"},
        )

        self.assertEqual(response.status_code, 201)

    def test_create_goal_missing_name_returns_422(self) -> None:
        """Test that missing goal_name returns 422 with readable error."""
        response = self.client.post(
            "/notion/goals",
            headers=self.auth_headers,
            json={"status": "Not started"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("goal_name", detail)
        self.assertIn("field required", detail)

    def test_create_goal_invalid_status_returns_422(self) -> None:
        """Test that invalid status enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/goals",
            headers=self.auth_headers,
            json={"goal_name": "Goal", "status": "Invalid"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("status", detail)
        self.assertIn("invalid value 'Invalid'", detail)

    def test_create_goal_progress_out_of_range_returns_422(self) -> None:
        """Test that progress outside 0-100 returns 422."""
        response = self.client.post(
            "/notion/goals",
            headers=self.auth_headers,
            json={"goal_name": "Goal", "progress": 150},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("progress", detail)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_goal_duplicate_name_returns_409(self, mock_client_class: MagicMock) -> None:
        """Test that duplicate goal name returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "existing-goal",
                "properties": {
                    "Goal name": {"title": [{"plain_text": "Existing Goal"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/goals",
            headers=self.auth_headers,
            json={"goal_name": "existing goal"},  # case insensitive match
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])


class TestUpdateGoalEndpoint(unittest.TestCase):
    """Tests for PATCH /notion/goals/{goal_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_goal_success(self, mock_client_class: MagicMock) -> None:
        """Test successful goal update."""
        mock_client = MagicMock()
        mock_client.update_page.return_value = {
            "id": "goal-123",
            "url": "https://notion.so/Goal",
            "properties": {
                "Goal name": {"title": [{"plain_text": "Goal"}]},
                "Status": {"status": {"name": "Done"}},
                "Priority": {"select": {"name": "Low"}},
                "Progress": {"number": 100},
                "Due date": {"date": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/goals/goal-123",
            headers=self.auth_headers,
            json={"status": "Done", "progress": 100},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "Done")
        self.assertEqual(data["progress"], 100)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_goal_no_fields_returns_400(self, mock_client_class: MagicMock) -> None:
        """Test that update with no fields returns 400."""
        mock_client_class.return_value = MagicMock()

        response = self.client.patch(
            "/notion/goals/goal-123",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No properties or content to update", response.json()["detail"])

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_goal_duplicate_name_returns_409(self, mock_client_class: MagicMock) -> None:
        """Test that updating to duplicate goal name returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "other-goal",
                "properties": {
                    "Goal name": {"title": [{"plain_text": "Other Goal"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/goals/goal-123",
            headers=self.auth_headers,
            json={"goal_name": "OTHER GOAL"},  # case insensitive match
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
