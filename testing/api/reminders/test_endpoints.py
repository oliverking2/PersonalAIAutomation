"""Tests for reminder API endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_TASK_DATA_SOURCE_ID", "test-data-source-id")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456789")

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.app import app
from src.database.reminders.models import ReminderInstance, ReminderSchedule, ReminderStatus


class TestCreateReminderEndpoint(unittest.TestCase):
    """Tests for POST /reminders endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_create_reminder_success(self, mock_get_session: MagicMock) -> None:
        """Test successful reminder creation."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()
        trigger_at = datetime.now(UTC) + timedelta(hours=1)

        with (
            patch("src.api.reminders.endpoints.create_reminder_schedule") as mock_create_schedule,
            patch("src.api.reminders.endpoints.create_reminder_instance") as mock_create_instance,
        ):
            mock_schedule = ReminderSchedule(
                id=schedule_id,
                message="Test reminder",
                chat_id=123456789,
                next_trigger_at=trigger_at,
                is_active=True,
                created_at=datetime.now(UTC),
            )
            mock_create_schedule.return_value = mock_schedule
            mock_create_instance.return_value = MagicMock()

            response = self.client.post(
                "/reminders",
                headers=self.auth_headers,
                json={
                    "message": "Test reminder",
                    "trigger_at": trigger_at.isoformat(),
                },
            )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["message"], "Test reminder")
        self.assertEqual(data["chat_id"], 123456789)
        self.assertFalse(data["is_recurring"])

    @patch("src.api.reminders.endpoints.get_session")
    def test_create_recurring_reminder(self, mock_get_session: MagicMock) -> None:
        """Test creating a recurring reminder with cron schedule."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()
        trigger_at = datetime.now(UTC) + timedelta(hours=1)

        with (
            patch("src.api.reminders.endpoints.create_reminder_schedule") as mock_create_schedule,
            patch("src.api.reminders.endpoints.create_reminder_instance"),
        ):
            mock_schedule = ReminderSchedule(
                id=schedule_id,
                message="Daily standup",
                chat_id=123456789,
                cron_schedule="0 9 * * 1-5",
                next_trigger_at=trigger_at,
                is_active=True,
                created_at=datetime.now(UTC),
            )
            mock_create_schedule.return_value = mock_schedule

            response = self.client.post(
                "/reminders",
                headers=self.auth_headers,
                json={
                    "message": "Daily standup",
                    "trigger_at": trigger_at.isoformat(),
                    "cron_schedule": "0 9 * * 1-5",
                },
            )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["cron_schedule"], "0 9 * * 1-5")
        self.assertTrue(data["is_recurring"])

    def test_create_reminder_missing_message_returns_422(self) -> None:
        """Test that missing message field returns 422."""
        trigger_at = datetime.now(UTC) + timedelta(hours=1)

        response = self.client.post(
            "/reminders",
            headers=self.auth_headers,
            json={"trigger_at": trigger_at.isoformat()},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("message", response.json()["detail"])


class TestQueryRemindersEndpoint(unittest.TestCase):
    """Tests for POST /reminders/query endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_query_reminders_success(self, mock_get_session: MagicMock) -> None:
        """Test successful reminder query."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.reminders.endpoints.list_schedules_for_chat") as mock_list:
            mock_list.return_value = [
                ReminderSchedule(
                    id=uuid4(),
                    message="Test",
                    chat_id=123456789,
                    next_trigger_at=datetime.now(UTC),
                    is_active=True,
                    created_at=datetime.now(UTC),
                )
            ]

            response = self.client.post(
                "/reminders/query",
                headers=self.auth_headers,
                json={},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)


class TestGetReminderEndpoint(unittest.TestCase):
    """Tests for GET /reminders/{reminder_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_get_reminder_success(self, mock_get_session: MagicMock) -> None:
        """Test successful reminder retrieval."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()

        with patch("src.api.reminders.endpoints.get_schedule_by_id") as mock_get:
            mock_get.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )

            response = self.client.get(
                f"/reminders/{schedule_id}",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Test")

    @patch("src.api.reminders.endpoints.get_session")
    def test_get_reminder_not_found_returns_404(self, mock_get_session: MagicMock) -> None:
        """Test that non-existent reminder returns 404."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.reminders.endpoints.get_schedule_by_id") as mock_get:
            mock_get.return_value = None

            response = self.client.get(
                f"/reminders/{uuid4()}",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 404)


class TestUpdateReminderEndpoint(unittest.TestCase):
    """Tests for PATCH /reminders/{reminder_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_update_reminder_message_success(self, mock_get_session: MagicMock) -> None:
        """Test successful update of reminder message."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()

        with patch("src.api.reminders.endpoints.update_reminder_schedule") as mock_update:
            mock_update.return_value = ReminderSchedule(
                id=schedule_id,
                message="Updated message",
                chat_id=123456789,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )

            response = self.client.patch(
                f"/reminders/{schedule_id}",
                headers=self.auth_headers,
                json={"message": "Updated message"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Updated message")

    @patch("src.api.reminders.endpoints.get_session")
    def test_update_reminder_cron_schedule_success(self, mock_get_session: MagicMock) -> None:
        """Test successful update of cron schedule."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()

        with patch("src.api.reminders.endpoints.update_reminder_schedule") as mock_update:
            mock_update.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                cron_schedule="0 9 * * 2",
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )

            response = self.client.patch(
                f"/reminders/{schedule_id}",
                headers=self.auth_headers,
                json={"cron_schedule": "0 9 * * 2"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["cron_schedule"], "0 9 * * 2")
        self.assertTrue(data["is_recurring"])

    @patch("src.api.reminders.endpoints.get_session")
    def test_update_reminder_clear_cron_schedule(self, mock_get_session: MagicMock) -> None:
        """Test clearing cron schedule to convert to one-time."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()

        with patch("src.api.reminders.endpoints.update_reminder_schedule") as mock_update:
            mock_update.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                cron_schedule=None,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )

            response = self.client.patch(
                f"/reminders/{schedule_id}",
                headers=self.auth_headers,
                json={"cron_schedule": ""},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["cron_schedule"])
        self.assertFalse(data["is_recurring"])

    @patch("src.api.reminders.endpoints.get_session")
    def test_update_reminder_not_found_returns_404(self, mock_get_session: MagicMock) -> None:
        """Test that updating non-existent reminder returns 404."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.reminders.endpoints.update_reminder_schedule") as mock_update:
            mock_update.return_value = None

            response = self.client.patch(
                f"/reminders/{uuid4()}",
                headers=self.auth_headers,
                json={"message": "Test"},
            )

        self.assertEqual(response.status_code, 404)

    def test_update_reminder_no_fields_returns_400(self) -> None:
        """Test that updating with no fields returns 400."""
        schedule_id = uuid4()

        response = self.client.patch(
            f"/reminders/{schedule_id}",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("At least one field", response.json()["detail"])

    def test_update_reminder_empty_message_returns_422(self) -> None:
        """Test that empty message returns 422."""
        schedule_id = uuid4()

        response = self.client.patch(
            f"/reminders/{schedule_id}",
            headers=self.auth_headers,
            json={"message": ""},
        )

        self.assertEqual(response.status_code, 422)


class TestCancelReminderEndpoint(unittest.TestCase):
    """Tests for DELETE /reminders/{reminder_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_cancel_reminder_success(self, mock_get_session: MagicMock) -> None:
        """Test successful reminder cancellation."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()

        with patch("src.api.reminders.endpoints.deactivate_schedule") as mock_deactivate:
            mock_deactivate.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                next_trigger_at=datetime.now(UTC),
                is_active=False,
                created_at=datetime.now(UTC),
            )

            response = self.client.delete(
                f"/reminders/{schedule_id}",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 204)

    @patch("src.api.reminders.endpoints.get_session")
    def test_cancel_reminder_not_found_returns_404(self, mock_get_session: MagicMock) -> None:
        """Test that cancelling non-existent reminder returns 404."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.reminders.endpoints.deactivate_schedule") as mock_deactivate:
            mock_deactivate.return_value = None

            response = self.client.delete(
                f"/reminders/{uuid4()}",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 404)


class TestAcknowledgeReminderEndpoint(unittest.TestCase):
    """Tests for POST /reminders/{reminder_id}/acknowledge endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_acknowledge_reminder_success(self, mock_get_session: MagicMock) -> None:
        """Test successful reminder acknowledgement."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()
        instance_id = uuid4()

        with (
            patch("src.api.reminders.endpoints.get_schedule_by_id") as mock_get_schedule,
            patch("src.api.reminders.endpoints.get_active_instance_for_schedule") as mock_get_inst,
            patch("src.api.reminders.endpoints.acknowledge_instance") as mock_ack,
            patch("src.api.reminders.endpoints.deactivate_schedule"),
        ):
            mock_get_schedule.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )
            mock_get_inst.return_value = ReminderInstance(
                id=instance_id,
                schedule_id=schedule_id,
                status=ReminderStatus.ACTIVE.value,
                next_send_at=datetime.now(UTC),
            )
            mock_ack.return_value = MagicMock()

            response = self.client.post(
                f"/reminders/{schedule_id}/acknowledge",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("acknowledged_at", data)

    @patch("src.api.reminders.endpoints.get_session")
    def test_acknowledge_no_active_instance_returns_400(self, mock_get_session: MagicMock) -> None:
        """Test that acknowledging with no active instance returns 400."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()

        with (
            patch("src.api.reminders.endpoints.get_schedule_by_id") as mock_get_schedule,
            patch("src.api.reminders.endpoints.get_active_instance_for_schedule") as mock_get_inst,
        ):
            mock_get_schedule.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )
            mock_get_inst.return_value = None

            response = self.client.post(
                f"/reminders/{schedule_id}/acknowledge",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No active instance", response.json()["detail"])


class TestSnoozeReminderEndpoint(unittest.TestCase):
    """Tests for POST /reminders/{reminder_id}/snooze endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_snooze_reminder_success(self, mock_get_session: MagicMock) -> None:
        """Test successful reminder snooze."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()
        instance_id = uuid4()

        with (
            patch("src.api.reminders.endpoints.get_schedule_by_id") as mock_get_schedule,
            patch("src.api.reminders.endpoints.get_active_instance_for_schedule") as mock_get_inst,
            patch("src.api.reminders.endpoints.snooze_instance") as mock_snooze,
        ):
            mock_get_schedule.return_value = ReminderSchedule(
                id=schedule_id,
                message="Test",
                chat_id=123456789,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
                created_at=datetime.now(UTC),
            )
            mock_get_inst.return_value = ReminderInstance(
                id=instance_id,
                schedule_id=schedule_id,
                status=ReminderStatus.ACTIVE.value,
                next_send_at=datetime.now(UTC),
            )
            mock_snooze.return_value = MagicMock()

            response = self.client.post(
                f"/reminders/{schedule_id}/snooze",
                headers=self.auth_headers,
                json={"duration_minutes": 30},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("snoozed_until", data)

    def test_snooze_invalid_duration_returns_422(self) -> None:
        """Test that invalid snooze duration returns 422."""
        schedule_id = uuid4()

        response = self.client.post(
            f"/reminders/{schedule_id}/snooze",
            headers=self.auth_headers,
            json={"duration_minutes": 2},  # Less than minimum of 5
        )

        self.assertEqual(response.status_code, 422)


class TestAcknowledgeInstanceEndpoint(unittest.TestCase):
    """Tests for POST /reminders/instances/{instance_id}/acknowledge endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_acknowledge_instance_success(self, mock_get_session: MagicMock) -> None:
        """Test successful instance acknowledgement."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        schedule_id = uuid4()
        instance_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123456789,
            next_trigger_at=datetime.now(UTC),
            is_active=True,
            created_at=datetime.now(UTC),
        )

        with (
            patch("src.api.reminders.endpoints.get_instance_by_id") as mock_get_instance,
            patch("src.api.reminders.endpoints.acknowledge_instance") as mock_ack,
            patch("src.api.reminders.endpoints.deactivate_schedule"),
        ):
            mock_instance = ReminderInstance(
                id=instance_id,
                schedule_id=schedule_id,
                status=ReminderStatus.ACTIVE.value,
                next_send_at=datetime.now(UTC),
            )
            mock_instance.schedule = mock_schedule
            mock_get_instance.return_value = mock_instance
            mock_ack.return_value = MagicMock()

            response = self.client.post(
                f"/reminders/instances/{instance_id}/acknowledge",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)

    @patch("src.api.reminders.endpoints.get_session")
    def test_acknowledge_already_resolved_returns_400(self, mock_get_session: MagicMock) -> None:
        """Test that acknowledging already resolved instance returns 400."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        instance_id = uuid4()

        with patch("src.api.reminders.endpoints.get_instance_by_id") as mock_get_instance:
            mock_get_instance.return_value = ReminderInstance(
                id=instance_id,
                schedule_id=uuid4(),
                status=ReminderStatus.ACKNOWLEDGED.value,
                next_send_at=datetime.now(UTC),
            )

            response = self.client.post(
                f"/reminders/instances/{instance_id}/acknowledge",
                headers=self.auth_headers,
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already resolved", response.json()["detail"])


class TestSnoozeInstanceEndpoint(unittest.TestCase):
    """Tests for POST /reminders/instances/{instance_id}/snooze endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.reminders.endpoints.get_session")
    def test_snooze_instance_success(self, mock_get_session: MagicMock) -> None:
        """Test successful instance snooze."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        instance_id = uuid4()

        with (
            patch("src.api.reminders.endpoints.get_instance_by_id") as mock_get_instance,
            patch("src.api.reminders.endpoints.snooze_instance") as mock_snooze,
        ):
            mock_get_instance.return_value = ReminderInstance(
                id=instance_id,
                schedule_id=uuid4(),
                status=ReminderStatus.ACTIVE.value,
                next_send_at=datetime.now(UTC),
            )
            mock_snooze.return_value = MagicMock()

            response = self.client.post(
                f"/reminders/instances/{instance_id}/snooze",
                headers=self.auth_headers,
                json={"duration_minutes": 60},
            )

        self.assertEqual(response.status_code, 200)

    @patch("src.api.reminders.endpoints.get_session")
    def test_snooze_already_resolved_returns_400(self, mock_get_session: MagicMock) -> None:
        """Test that snoozing already resolved instance returns 400."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        instance_id = uuid4()

        with patch("src.api.reminders.endpoints.get_instance_by_id") as mock_get_instance:
            mock_get_instance.return_value = ReminderInstance(
                id=instance_id,
                schedule_id=uuid4(),
                status=ReminderStatus.EXPIRED.value,
                next_send_at=datetime.now(UTC),
            )

            response = self.client.post(
                f"/reminders/instances/{instance_id}/snooze",
                headers=self.auth_headers,
                json={"duration_minutes": 60},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already resolved", response.json()["detail"])


class TestAuthenticationRequired(unittest.TestCase):
    """Tests for authentication on reminder endpoints."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)

    def test_create_reminder_without_auth_returns_401(self) -> None:
        """Test that creating reminder without auth returns 401."""
        response = self.client.post("/reminders", json={"message": "Test"})
        self.assertEqual(response.status_code, 401)

    def test_query_reminders_without_auth_returns_401(self) -> None:
        """Test that querying reminders without auth returns 401."""
        response = self.client.post("/reminders/query", json={})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
