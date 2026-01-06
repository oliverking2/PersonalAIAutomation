"""Tests for Telegram callback handlers."""

import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Set required env var before imports that trigger module loading
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("GRAPH_TARGET_UPN", "test@example.com")

from src.telegram.callbacks import (
    REMINDER_CALLBACK_PREFIX,
    CallbackResult,
    ReminderAction,
    _calculate_snooze_time,
    _get_tomorrow_morning,
    handle_reminder_callback,
    parse_reminder_callback,
)


class TestParseReminderCallback(unittest.TestCase):
    """Tests for parse_reminder_callback function."""

    def test_returns_none_for_non_reminder_callback(self) -> None:
        """Test that non-reminder callbacks return None."""
        result = parse_reminder_callback("other:action:123")

        self.assertIsNone(result)

    def test_returns_none_for_empty_string(self) -> None:
        """Test that empty string returns None."""
        result = parse_reminder_callback("")

        self.assertIsNone(result)

    def test_returns_none_for_insufficient_parts(self) -> None:
        """Test that callback with too few parts returns None."""
        result = parse_reminder_callback("remind:ack")

        self.assertIsNone(result)

    def test_parses_acknowledge_callback(self) -> None:
        """Test parsing an acknowledge callback."""
        instance_id = uuid4()
        data = f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}"

        result = parse_reminder_callback(data)

        self.assertIsNotNone(result)
        action, parsed_id, param = result  # type: ignore[misc]
        self.assertEqual(action, ReminderAction.ACKNOWLEDGE)
        self.assertEqual(parsed_id, instance_id)
        self.assertIsNone(param)

    def test_parses_snooze_callback_with_minutes(self) -> None:
        """Test parsing a snooze callback with minutes parameter."""
        instance_id = uuid4()
        data = f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:60"

        result = parse_reminder_callback(data)

        self.assertIsNotNone(result)
        action, parsed_id, param = result  # type: ignore[misc]
        self.assertEqual(action, ReminderAction.SNOOZE)
        self.assertEqual(parsed_id, instance_id)
        self.assertEqual(param, "60")

    def test_parses_snooze_callback_with_tomorrow(self) -> None:
        """Test parsing a snooze callback with tomorrow parameter."""
        instance_id = uuid4()
        data = f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:tomorrow"

        result = parse_reminder_callback(data)

        self.assertIsNotNone(result)
        action, parsed_id, param = result  # type: ignore[misc]
        self.assertEqual(action, ReminderAction.SNOOZE)
        self.assertEqual(parsed_id, instance_id)
        self.assertEqual(param, "tomorrow")

    def test_returns_none_for_invalid_uuid(self) -> None:
        """Test that invalid UUID returns None."""
        data = f"{REMINDER_CALLBACK_PREFIX}ack:not-a-valid-uuid"

        result = parse_reminder_callback(data)

        self.assertIsNone(result)

    def test_returns_none_for_invalid_action(self) -> None:
        """Test that invalid action returns None."""
        instance_id = uuid4()
        data = f"{REMINDER_CALLBACK_PREFIX}invalid:{instance_id}"

        result = parse_reminder_callback(data)

        self.assertIsNone(result)


class TestGetTomorrowMorning(unittest.TestCase):
    """Tests for _get_tomorrow_morning function."""

    def test_returns_8am_utc(self) -> None:
        """Test that returned time is 8am."""
        result = _get_tomorrow_morning()

        self.assertEqual(result.hour, 8)
        self.assertEqual(result.minute, 0)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)

    def test_returns_tomorrow(self) -> None:
        """Test that returned date is tomorrow."""
        now = datetime.now(UTC)
        result = _get_tomorrow_morning()

        expected_date = (now + timedelta(days=1)).date()
        self.assertEqual(result.date(), expected_date)


class TestCalculateSnoozeTime(unittest.TestCase):
    """Tests for _calculate_snooze_time function."""

    def test_tomorrow_parameter(self) -> None:
        """Test snooze until tomorrow morning."""
        snooze_until, description = _calculate_snooze_time("tomorrow")

        self.assertEqual(snooze_until.hour, 8)
        self.assertEqual(description, "tomorrow morning")

    def test_60_minutes(self) -> None:
        """Test snooze for 60 minutes shows hours."""
        _, description = _calculate_snooze_time("60")

        self.assertEqual(description, "1h")

    def test_180_minutes(self) -> None:
        """Test snooze for 180 minutes shows hours."""
        _, description = _calculate_snooze_time("180")

        self.assertEqual(description, "3h")

    def test_30_minutes(self) -> None:
        """Test snooze for 30 minutes shows minutes."""
        _, description = _calculate_snooze_time("30")

        self.assertEqual(description, "30m")

    def test_none_defaults_to_60_minutes(self) -> None:
        """Test that None parameter defaults to 60 minutes."""
        _, description = _calculate_snooze_time(None)

        self.assertEqual(description, "1h")

    def test_invalid_parameter_defaults_to_60_minutes(self) -> None:
        """Test that invalid parameter defaults to 60 minutes."""
        _, description = _calculate_snooze_time("invalid")

        self.assertEqual(description, "1h")


class TestCallbackResult(unittest.TestCase):
    """Tests for CallbackResult class."""

    def test_default_values(self) -> None:
        """Test default values."""
        result = CallbackResult(answer_text="Test")

        self.assertEqual(result.answer_text, "Test")
        self.assertFalse(result.show_alert)
        self.assertIsNone(result.edit_text)

    def test_all_values(self) -> None:
        """Test setting all values."""
        result = CallbackResult(
            answer_text="Test",
            show_alert=True,
            edit_text="Edited",
        )

        self.assertEqual(result.answer_text, "Test")
        self.assertTrue(result.show_alert)
        self.assertEqual(result.edit_text, "Edited")


class TestHandleReminderCallback(unittest.TestCase):
    """Tests for handle_reminder_callback function."""

    def test_invalid_callback_data(self) -> None:
        """Test handling invalid callback data."""
        result = handle_reminder_callback("invalid:data")

        self.assertEqual(result.answer_text, "Invalid callback data")
        self.assertTrue(result.show_alert)

    @patch("src.telegram.callbacks.get_session")
    def test_reminder_not_found(self, mock_get_session: MagicMock) -> None:
        """Test handling when reminder instance not found."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        with patch("src.telegram.callbacks.get_instance_by_id", return_value=None):
            instance_id = uuid4()
            data = f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}"

            result = handle_reminder_callback(data)

        self.assertEqual(result.answer_text, "Reminder not found")
        self.assertTrue(result.show_alert)

    @patch("src.telegram.callbacks.get_session")
    def test_already_acknowledged(self, mock_get_session: MagicMock) -> None:
        """Test handling already acknowledged reminder."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_instance = MagicMock()
        mock_instance.status = "acknowledged"

        with patch("src.telegram.callbacks.get_instance_by_id", return_value=mock_instance):
            instance_id = uuid4()
            data = f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}"

            result = handle_reminder_callback(data)

        self.assertIn("already acknowledged", result.answer_text)
        self.assertTrue(result.show_alert)

    @patch("src.telegram.callbacks.get_session")
    @patch("src.telegram.callbacks.acknowledge_instance")
    @patch("src.telegram.callbacks.deactivate_schedule")
    def test_acknowledge_one_time_reminder(
        self,
        mock_deactivate: MagicMock,
        mock_acknowledge: MagicMock,
        mock_get_session: MagicMock,
    ) -> None:
        """Test acknowledging a one-time reminder deactivates the schedule."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_schedule = MagicMock()
        mock_schedule.is_recurring = False
        mock_schedule.id = uuid4()

        mock_instance = MagicMock()
        mock_instance.status = "active"
        mock_instance.schedule = mock_schedule

        instance_id = uuid4()

        with patch("src.telegram.callbacks.get_instance_by_id", return_value=mock_instance):
            data = f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}"

            result = handle_reminder_callback(data, original_text="Test message")

        self.assertEqual(result.answer_text, "Reminder acknowledged!")
        self.assertIn("Acknowledged", result.edit_text or "")
        mock_acknowledge.assert_called_once()
        mock_deactivate.assert_called_once_with(mock_session, mock_schedule.id)

    @patch("src.telegram.callbacks.get_session")
    @patch("src.telegram.callbacks.acknowledge_instance")
    @patch("src.telegram.callbacks.deactivate_schedule")
    def test_acknowledge_recurring_reminder(
        self,
        mock_deactivate: MagicMock,
        mock_acknowledge: MagicMock,
        mock_get_session: MagicMock,
    ) -> None:
        """Test acknowledging a recurring reminder does not deactivate the schedule."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_schedule = MagicMock()
        mock_schedule.is_recurring = True

        mock_instance = MagicMock()
        mock_instance.status = "active"
        mock_instance.schedule = mock_schedule

        instance_id = uuid4()

        with patch("src.telegram.callbacks.get_instance_by_id", return_value=mock_instance):
            data = f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}"

            result = handle_reminder_callback(data)

        self.assertEqual(result.answer_text, "Reminder acknowledged!")
        mock_acknowledge.assert_called_once()
        mock_deactivate.assert_not_called()

    @patch("src.telegram.callbacks.get_session")
    @patch("src.telegram.callbacks.snooze_instance")
    def test_snooze_reminder(
        self,
        mock_snooze: MagicMock,
        mock_get_session: MagicMock,
    ) -> None:
        """Test snoozing a reminder."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_schedule = MagicMock()
        mock_instance = MagicMock()
        mock_instance.status = "active"
        mock_instance.schedule = mock_schedule

        instance_id = uuid4()

        with patch("src.telegram.callbacks.get_instance_by_id", return_value=mock_instance):
            data = f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:60"

            result = handle_reminder_callback(data, original_text="Test message")

        self.assertIn("Snoozed", result.answer_text)
        self.assertIn("Snoozed until", result.edit_text or "")
        mock_snooze.assert_called_once()


if __name__ == "__main__":
    unittest.main()
