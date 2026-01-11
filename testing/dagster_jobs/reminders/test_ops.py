"""Tests for reminder Dagster ops."""

import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Set required env vars before importing src.dagster modules
os.environ.setdefault("GRAPH_TARGET_UPN", "test@example.com")

from dagster import build_op_context
from src.dagster.reminders.ops import (
    REMINDER_CALLBACK_PREFIX,
    ReminderStats,
    _build_reminder_keyboard,
    _format_reminder_message,
    calculate_next_cron_trigger,
    process_reminders_op,
)
from src.database.reminders.models import ReminderInstance, ReminderSchedule, ReminderStatus


class TestCalculateNextCronTrigger(unittest.TestCase):
    """Tests for calculate_next_cron_trigger function."""

    def test_every_5_minutes_from_start_of_hour(self) -> None:
        """Test next trigger for */5 * * * * from start of hour."""
        base_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=UTC)
        result = calculate_next_cron_trigger("*/5 * * * *", base_time)

        self.assertEqual(result, datetime(2025, 1, 6, 12, 5, 0, tzinfo=UTC))

    def test_every_5_minutes_mid_interval(self) -> None:
        """Test next trigger for */5 * * * * from middle of interval."""
        base_time = datetime(2025, 1, 6, 12, 3, 0, tzinfo=UTC)
        result = calculate_next_cron_trigger("*/5 * * * *", base_time)

        self.assertEqual(result, datetime(2025, 1, 6, 12, 5, 0, tzinfo=UTC))

    def test_daily_at_9am(self) -> None:
        """Test next trigger for 0 9 * * * (daily at 9am)."""
        base_time = datetime(2025, 1, 6, 10, 0, 0, tzinfo=UTC)
        result = calculate_next_cron_trigger("0 9 * * *", base_time)

        # Should be next day at 9am
        self.assertEqual(result, datetime(2025, 1, 7, 9, 0, 0, tzinfo=UTC))

    def test_weekly_monday_morning(self) -> None:
        """Test next trigger for 0 8 * * 1 (Monday 8am)."""
        # Tuesday Jan 7, 2025
        base_time = datetime(2025, 1, 7, 10, 0, 0, tzinfo=UTC)
        result = calculate_next_cron_trigger("0 8 * * 1", base_time)

        # Should be Monday Jan 13, 2025 at 8am
        self.assertEqual(result, datetime(2025, 1, 13, 8, 0, 0, tzinfo=UTC))

    def test_result_is_timezone_aware(self) -> None:
        """Test that result is timezone aware."""
        base_time = datetime(2025, 1, 6, 12, 0, 0, tzinfo=UTC)
        result = calculate_next_cron_trigger("*/5 * * * *", base_time)

        self.assertIsNotNone(result.tzinfo)

    def test_defaults_to_now_when_no_after_provided(self) -> None:
        """Test that function uses current time when after is None."""
        now = datetime.now(UTC)
        result = calculate_next_cron_trigger("*/5 * * * *")

        # Result should be within the next 5 minutes
        self.assertGreater(result, now)
        self.assertLessEqual(result, now + timedelta(minutes=5))


class TestFormatReminderMessage(unittest.TestCase):
    """Tests for _format_reminder_message function."""

    def test_formats_message_with_send_count(self) -> None:
        """Test that message includes send count.

        send_count is incremented after sending, so display shows send_count + 1.
        With send_count=1, this would be the 2nd send.
        """
        schedule = ReminderSchedule(
            id=uuid4(),
            message="Test reminder message",
            chat_id=123456,
            next_trigger_at=datetime.now(UTC),
        )
        instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            send_count=1,
            max_sends=3,
            next_send_at=datetime.now(UTC),
        )

        result = _format_reminder_message(schedule, instance)

        self.assertIn("**Reminder**", result)
        self.assertIn("(Send 2/3)", result)
        self.assertIn("Test reminder message", result)

    def test_formats_first_send(self) -> None:
        """Test message format for first send.

        send_count=0 means it hasn't been sent yet, so display shows 1/3.
        """
        schedule = ReminderSchedule(
            id=uuid4(),
            message="First reminder",
            chat_id=789,
            next_trigger_at=datetime.now(UTC),
        )
        instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            send_count=0,
            max_sends=3,
            next_send_at=datetime.now(UTC),
        )

        result = _format_reminder_message(schedule, instance)

        self.assertIn("(Send 1/3)", result)
        self.assertIn("First reminder", result)


class TestBuildReminderKeyboard(unittest.TestCase):
    """Tests for _build_reminder_keyboard function."""

    def test_creates_keyboard_with_four_buttons(self) -> None:
        """Test that keyboard has 4 buttons in 2 rows."""
        instance_id = str(uuid4())
        keyboard = _build_reminder_keyboard(instance_id)

        self.assertEqual(len(keyboard.inline_keyboard), 2)
        self.assertEqual(len(keyboard.inline_keyboard[0]), 2)
        self.assertEqual(len(keyboard.inline_keyboard[1]), 2)

    def test_done_button_has_correct_callback_data(self) -> None:
        """Test that Done button has acknowledge callback data."""
        instance_id = str(uuid4())
        keyboard = _build_reminder_keyboard(instance_id)

        done_button = keyboard.inline_keyboard[0][0]
        self.assertEqual(done_button.text, "Done")
        self.assertEqual(done_button.callback_data, f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}")

    def test_snooze_1h_button_has_correct_callback_data(self) -> None:
        """Test that Snooze 1h button has correct callback data."""
        instance_id = str(uuid4())
        keyboard = _build_reminder_keyboard(instance_id)

        snooze_button = keyboard.inline_keyboard[0][1]
        self.assertEqual(snooze_button.text, "Snooze 1h")
        self.assertEqual(
            snooze_button.callback_data,
            f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:60",
        )

    def test_snooze_3h_button_has_correct_callback_data(self) -> None:
        """Test that Snooze 3h button has correct callback data."""
        instance_id = str(uuid4())
        keyboard = _build_reminder_keyboard(instance_id)

        snooze_button = keyboard.inline_keyboard[1][0]
        self.assertEqual(snooze_button.text, "Snooze 3h")
        self.assertEqual(
            snooze_button.callback_data,
            f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:180",
        )

    def test_tomorrow_button_has_correct_callback_data(self) -> None:
        """Test that Tomorrow button has correct callback data."""
        instance_id = str(uuid4())
        keyboard = _build_reminder_keyboard(instance_id)

        tomorrow_button = keyboard.inline_keyboard[1][1]
        self.assertEqual(tomorrow_button.text, "Tomorrow")
        self.assertEqual(
            tomorrow_button.callback_data,
            f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:tomorrow",
        )


class TestReminderStats(unittest.TestCase):
    """Tests for ReminderStats dataclass."""

    def test_default_values(self) -> None:
        """Test that defaults are initialized correctly."""
        stats = ReminderStats()

        self.assertEqual(stats.schedules_triggered, 0)
        self.assertEqual(stats.instances_created, 0)
        self.assertEqual(stats.reminders_sent, 0)
        self.assertEqual(stats.reminders_expired, 0)
        self.assertEqual(stats.errors, [])

    def test_custom_values(self) -> None:
        """Test initialization with custom values."""
        stats = ReminderStats(
            schedules_triggered=5,
            instances_created=3,
            reminders_sent=2,
            reminders_expired=1,
            errors=["error1", "error2"],
        )

        self.assertEqual(stats.schedules_triggered, 5)
        self.assertEqual(stats.instances_created, 3)
        self.assertEqual(stats.reminders_sent, 2)
        self.assertEqual(stats.reminders_expired, 1)
        self.assertEqual(stats.errors, ["error1", "error2"])


class TestProcessRemindersOp(unittest.TestCase):
    """Tests for process_reminders_op."""

    @patch("src.dagster.reminders.ops.get_telegram_settings")
    @patch("src.dagster.reminders.ops.TelegramClient")
    @patch("src.dagster.reminders.ops.get_session")
    @patch("src.dagster.reminders.ops.get_schedules_to_trigger")
    @patch("src.dagster.reminders.ops.get_instances_to_send")
    def test_returns_stats_with_no_work(
        self,
        mock_get_instances: MagicMock,
        mock_get_schedules: MagicMock,
        mock_get_session: MagicMock,
        mock_telegram_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test op returns empty stats when no reminders to process."""
        mock_settings.return_value = MagicMock(
            bot_token="test-token",
            chat_id="123456",
            error_bot_token=None,
            error_chat_id=None,
        )
        mock_get_schedules.return_value = []
        mock_get_instances.return_value = []
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        context = build_op_context()
        result = process_reminders_op(context)

        self.assertEqual(result.schedules_triggered, 0)
        self.assertEqual(result.instances_created, 0)
        self.assertEqual(result.reminders_sent, 0)
        self.assertEqual(result.errors, [])

    @patch("src.dagster.reminders.ops.get_telegram_settings")
    @patch("src.dagster.reminders.ops.TelegramClient")
    @patch("src.dagster.reminders.ops.get_session")
    @patch("src.dagster.reminders.ops.get_schedules_to_trigger")
    @patch("src.dagster.reminders.ops.get_instances_to_send")
    @patch("src.dagster.reminders.ops.get_active_instance_for_schedule")
    @patch("src.dagster.reminders.ops.create_reminder_instance")
    def test_creates_instance_for_triggered_schedule(  # noqa: PLR0913
        self,
        mock_create_instance: MagicMock,
        mock_get_active: MagicMock,
        mock_get_instances: MagicMock,
        mock_get_schedules: MagicMock,
        mock_get_session: MagicMock,
        mock_telegram_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that instance is created when schedule triggers."""
        mock_settings.return_value = MagicMock(
            bot_token="test-token",
            chat_id="123456",
            error_bot_token=None,
            error_chat_id=None,
        )

        schedule = ReminderSchedule(
            id=uuid4(),
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        mock_get_schedules.return_value = [schedule]
        mock_get_active.return_value = None  # No existing active instance
        mock_get_instances.return_value = []

        new_instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            next_send_at=datetime.now(UTC),
        )
        mock_create_instance.return_value = new_instance

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        context = build_op_context()
        result = process_reminders_op(context)

        self.assertEqual(result.schedules_triggered, 1)
        self.assertEqual(result.instances_created, 1)
        mock_create_instance.assert_called_once()

    @patch("src.dagster.reminders.ops.get_telegram_settings")
    @patch("src.dagster.reminders.ops.TelegramClient")
    @patch("src.dagster.reminders.ops.get_session")
    @patch("src.dagster.reminders.ops.get_schedules_to_trigger")
    @patch("src.dagster.reminders.ops.get_instances_to_send")
    @patch("src.dagster.reminders.ops.get_active_instance_for_schedule")
    def test_skips_schedule_with_existing_active_instance(  # noqa: PLR0913
        self,
        mock_get_active: MagicMock,
        mock_get_instances: MagicMock,
        mock_get_schedules: MagicMock,
        mock_get_session: MagicMock,
        mock_telegram_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that schedule is skipped if it has an active instance."""
        mock_settings.return_value = MagicMock(
            bot_token="test-token",
            chat_id="123456",
            error_bot_token=None,
            error_chat_id=None,
        )

        schedule = ReminderSchedule(
            id=uuid4(),
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        existing_instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            status=ReminderStatus.ACTIVE.value,
            next_send_at=datetime.now(UTC),
        )

        mock_get_schedules.return_value = [schedule]
        mock_get_active.return_value = existing_instance
        mock_get_instances.return_value = []

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        context = build_op_context()
        result = process_reminders_op(context)

        self.assertEqual(result.schedules_triggered, 1)
        self.assertEqual(result.instances_created, 0)

    @patch("src.dagster.reminders.ops.get_telegram_settings")
    @patch("src.dagster.reminders.ops.TelegramClient")
    @patch("src.dagster.reminders.ops.get_session")
    @patch("src.dagster.reminders.ops.get_schedules_to_trigger")
    @patch("src.dagster.reminders.ops.get_instances_to_send")
    @patch("src.dagster.reminders.ops.mark_instance_sent")
    @patch("src.dagster.reminders.ops._send_reminder")
    def test_sends_reminder_for_pending_instance(  # noqa: PLR0913
        self,
        mock_send_reminder: MagicMock,
        mock_mark_sent: MagicMock,
        mock_get_instances: MagicMock,
        mock_get_schedules: MagicMock,
        mock_get_session: MagicMock,
        mock_telegram_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that reminder is sent for pending instance."""
        mock_settings.return_value = MagicMock(
            bot_token="test-token",
            chat_id="123456",
            error_bot_token=None,
            error_chat_id=None,
        )

        schedule = ReminderSchedule(
            id=uuid4(),
            message="Test message",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
        )
        instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            status=ReminderStatus.PENDING.value,
            send_count=0,
            max_sends=3,
            next_send_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        instance.schedule = schedule

        mock_get_schedules.return_value = []
        mock_get_instances.return_value = [instance]

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        context = build_op_context()
        result = process_reminders_op(context)

        self.assertEqual(result.reminders_sent, 1)
        mock_send_reminder.assert_called_once()
        mock_mark_sent.assert_called_once()

    @patch("src.dagster.reminders.ops.get_telegram_settings")
    @patch("src.dagster.reminders.ops.TelegramClient")
    @patch("src.dagster.reminders.ops.get_session")
    @patch("src.dagster.reminders.ops.get_schedules_to_trigger")
    @patch("src.dagster.reminders.ops.get_instances_to_send")
    @patch("src.dagster.reminders.ops.expire_instance")
    def test_expires_instance_at_max_sends(  # noqa: PLR0913
        self,
        mock_expire: MagicMock,
        mock_get_instances: MagicMock,
        mock_get_schedules: MagicMock,
        mock_get_session: MagicMock,
        mock_telegram_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that instance is expired when max sends reached."""
        mock_settings.return_value = MagicMock(
            bot_token="test-token",
            chat_id="123456",
            error_bot_token=None,
            error_chat_id=None,
        )

        schedule = ReminderSchedule(
            id=uuid4(),
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
        )
        instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            status=ReminderStatus.ACTIVE.value,
            send_count=3,  # Already sent 3 times
            max_sends=3,
            next_send_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        instance.schedule = schedule

        mock_get_schedules.return_value = []
        mock_get_instances.return_value = [instance]

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        context = build_op_context()
        result = process_reminders_op(context)

        self.assertEqual(result.reminders_expired, 1)
        self.assertEqual(result.reminders_sent, 0)
        mock_expire.assert_called_once()

    @patch("src.dagster.reminders.ops.get_telegram_settings")
    @patch("src.dagster.reminders.ops.TelegramClient")
    @patch("src.dagster.reminders.ops.get_session")
    @patch("src.dagster.reminders.ops.get_schedules_to_trigger")
    @patch("src.dagster.reminders.ops.get_instances_to_send")
    @patch("src.dagster.reminders.ops.get_active_instance_for_schedule")
    @patch("src.dagster.reminders.ops.create_reminder_instance")
    @patch("src.dagster.reminders.ops.update_schedule_next_trigger")
    def test_updates_next_trigger_for_recurring_schedule(  # noqa: PLR0913
        self,
        mock_update_trigger: MagicMock,
        mock_create_instance: MagicMock,
        mock_get_active: MagicMock,
        mock_get_instances: MagicMock,
        mock_get_schedules: MagicMock,
        mock_get_session: MagicMock,
        mock_telegram_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that recurring schedule next trigger is updated."""
        mock_settings.return_value = MagicMock(
            bot_token="test-token",
            chat_id="123456",
            error_bot_token=None,
            error_chat_id=None,
        )

        schedule = ReminderSchedule(
            id=uuid4(),
            message="Daily reminder",
            chat_id=123,
            next_trigger_at=datetime.now(UTC) - timedelta(minutes=1),
            cron_schedule="0 9 * * *",  # Daily at 9am
        )

        mock_get_schedules.return_value = [schedule]
        mock_get_active.return_value = None
        mock_get_instances.return_value = []

        new_instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule.id,
            next_send_at=datetime.now(UTC),
        )
        mock_create_instance.return_value = new_instance

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        context = build_op_context()
        process_reminders_op(context)

        mock_update_trigger.assert_called_once()


if __name__ == "__main__":
    unittest.main()
