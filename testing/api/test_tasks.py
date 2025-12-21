"""Tests for task trigger endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app


class TestTaskEndpointsAuth(unittest.TestCase):
    """Tests for task endpoint authentication."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_process_newsletters_requires_auth(self) -> None:
        """Test that endpoint requires Bearer token."""
        response = self.client.post("/tasks/process-newsletters")
        # HTTPBearer returns 401 when no credentials provided
        self.assertIn(response.status_code, [401, 403])

    def test_send_alerts_requires_auth(self) -> None:
        """Test that send-alerts endpoint requires Bearer token."""
        response = self.client.post("/tasks/send-alerts")
        self.assertIn(response.status_code, [401, 403])

    def test_task_status_requires_auth(self) -> None:
        """Test that task status endpoint requires Bearer token."""
        response = self.client.get("/tasks/some-task-id")
        self.assertIn(response.status_code, [401, 403])

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    def test_invalid_token_returns_401(self) -> None:
        """Test that invalid token returns 401."""
        response = self.client.post(
            "/tasks/process-newsletters",
            headers={"Authorization": "Bearer wrong-token"},
        )
        self.assertEqual(response.status_code, 401)


class TestProcessNewslettersEndpoint(unittest.TestCase):
    """Tests for /tasks/process-newsletters endpoint."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-token"}

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.process_newsletters_task")
    def test_triggers_task_with_default_days(self, mock_task: MagicMock) -> None:
        """Test that task is triggered with default days_back."""
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_task.delay.return_value = mock_result

        response = self.client.post(
            "/tasks/process-newsletters",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 202)
        mock_task.delay.assert_called_once_with(days_back=1)

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.process_newsletters_task")
    def test_triggers_task_with_custom_days(self, mock_task: MagicMock) -> None:
        """Test that task is triggered with custom days_back."""
        mock_result = MagicMock()
        mock_result.id = "task-456"
        mock_task.delay.return_value = mock_result

        response = self.client.post(
            "/tasks/process-newsletters",
            headers=self.auth_headers,
            json={"days_back": 7},
        )

        self.assertEqual(response.status_code, 202)
        mock_task.delay.assert_called_once_with(days_back=7)

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.process_newsletters_task")
    def test_returns_task_id_in_response(self, mock_task: MagicMock) -> None:
        """Test that response contains task ID."""
        mock_result = MagicMock()
        mock_result.id = "task-789"
        mock_task.delay.return_value = mock_result

        response = self.client.post(
            "/tasks/process-newsletters",
            headers=self.auth_headers,
        )

        data = response.json()
        self.assertEqual(data["task_id"], "task-789")
        self.assertEqual(data["task_name"], "process_newsletters_task")
        self.assertEqual(data["status"], "queued")

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    def test_rejects_invalid_days_back_zero(self) -> None:
        """Test that days_back of 0 is rejected."""
        response = self.client.post(
            "/tasks/process-newsletters",
            headers=self.auth_headers,
            json={"days_back": 0},
        )
        self.assertEqual(response.status_code, 422)

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    def test_rejects_invalid_days_back_too_large(self) -> None:
        """Test that days_back over 30 is rejected."""
        response = self.client.post(
            "/tasks/process-newsletters",
            headers=self.auth_headers,
            json={"days_back": 31},
        )
        self.assertEqual(response.status_code, 422)


class TestSendAlertsEndpoint(unittest.TestCase):
    """Tests for /tasks/send-alerts endpoint."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-token"}

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.send_alerts_task")
    def test_triggers_send_alerts_task(self, mock_task: MagicMock) -> None:
        """Test that send alerts task is triggered."""
        mock_result = MagicMock()
        mock_result.id = "task-abc"
        mock_task.delay.return_value = mock_result

        response = self.client.post(
            "/tasks/send-alerts",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 202)
        mock_task.delay.assert_called_once()

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.send_alerts_task")
    def test_returns_task_details(self, mock_task: MagicMock) -> None:
        """Test that response contains task details."""
        mock_result = MagicMock()
        mock_result.id = "task-def"
        mock_task.delay.return_value = mock_result

        response = self.client.post(
            "/tasks/send-alerts",
            headers=self.auth_headers,
        )

        data = response.json()
        self.assertEqual(data["task_id"], "task-def")
        self.assertEqual(data["task_name"], "send_alerts_task")


class TestTaskStatusEndpoint(unittest.TestCase):
    """Tests for /tasks/{task_id} endpoint."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-token"}

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.AsyncResult")
    def test_returns_pending_status(self, mock_async_result: MagicMock) -> None:
        """Test that pending task status is returned."""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None
        mock_async_result.return_value = mock_result

        response = self.client.get(
            "/tasks/task-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["task_id"], "task-123")
        self.assertEqual(data["status"], "PENDING")
        self.assertIsNone(data["result"])

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.AsyncResult")
    def test_returns_success_status_with_result(self, mock_async_result: MagicMock) -> None:
        """Test that successful task returns result."""
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"newsletters_processed": 5, "articles_new": 10}
        mock_async_result.return_value = mock_result

        response = self.client.get(
            "/tasks/task-456",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["result"]["newsletters_processed"], 5)

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    @patch("src.api.tasks.endpoints.AsyncResult")
    def test_returns_failure_status(self, mock_async_result: MagicMock) -> None:
        """Test that failed task status is returned."""
        mock_result = MagicMock()
        mock_result.state = "FAILURE"
        mock_result.result = None
        mock_async_result.return_value = mock_result

        response = self.client.get(
            "/tasks/task-789",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "FAILURE")


if __name__ == "__main__":
    unittest.main()
