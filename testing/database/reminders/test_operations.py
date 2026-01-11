"""Tests for reminder database operations."""

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from src.database.reminders.models import ReminderInstance, ReminderSchedule, ReminderStatus
from src.database.reminders.operations import (
    RESEND_INTERVAL_MINUTES,
    acknowledge_instance,
    create_reminder_instance,
    create_reminder_schedule,
    deactivate_schedule,
    expire_instance,
    get_active_instance_for_schedule,
    get_instance_by_id,
    get_instances_to_send,
    get_schedule_by_id,
    get_schedules_to_trigger,
    list_schedules_for_chat,
    mark_instance_sent,
    snooze_instance,
    update_reminder_schedule,
    update_schedule_next_trigger,
)


class TestCreateReminderSchedule(unittest.TestCase):
    """Tests for create_reminder_schedule operation."""

    def test_creates_schedule_with_required_fields(self) -> None:
        """Test creating a one-time schedule."""
        mock_session = MagicMock()
        trigger_at = datetime.now(UTC) + timedelta(hours=1)

        schedule = create_reminder_schedule(
            session=mock_session,
            message="Test reminder",
            chat_id=123456,
            trigger_at=trigger_at,
        )

        self.assertEqual(schedule.message, "Test reminder")
        self.assertEqual(schedule.chat_id, 123456)
        self.assertEqual(schedule.next_trigger_at, trigger_at)
        self.assertIsNone(schedule.cron_schedule)
        self.assertFalse(schedule.is_recurring)
        mock_session.add.assert_called_once_with(schedule)
        mock_session.flush.assert_called_once()

    def test_creates_recurring_schedule_with_cron(self) -> None:
        """Test creating a recurring schedule with cron expression."""
        mock_session = MagicMock()
        trigger_at = datetime.now(UTC)

        schedule = create_reminder_schedule(
            session=mock_session,
            message="Daily reminder",
            chat_id=789,
            trigger_at=trigger_at,
            cron_schedule="0 9 * * *",
        )

        self.assertEqual(schedule.cron_schedule, "0 9 * * *")
        self.assertTrue(schedule.is_recurring)


class TestCreateReminderInstance(unittest.TestCase):
    """Tests for create_reminder_instance operation."""

    def test_creates_instance_with_schedule(self) -> None:
        """Test creating an instance for a schedule."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
        )
        trigger_at = datetime.now(UTC)

        instance = create_reminder_instance(
            session=mock_session,
            schedule=mock_schedule,
            trigger_at=trigger_at,
        )

        self.assertEqual(instance.schedule_id, schedule_id)
        self.assertEqual(instance.next_send_at, trigger_at)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


class TestGetScheduleById(unittest.TestCase):
    """Tests for get_schedule_by_id operation."""

    def test_returns_schedule_when_found(self) -> None:
        """Test that schedule is returned when found."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        result = get_schedule_by_id(mock_session, schedule_id)

        self.assertEqual(result, mock_schedule)

    def test_returns_none_when_not_found(self) -> None:
        """Test that None is returned when schedule not found."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = get_schedule_by_id(mock_session, uuid4())

        self.assertIsNone(result)


class TestGetInstanceById(unittest.TestCase):
    """Tests for get_instance_by_id operation."""

    def test_returns_instance_when_found(self) -> None:
        """Test that instance is returned when found."""
        mock_session = MagicMock()
        instance_id = uuid4()
        mock_instance = ReminderInstance(
            id=instance_id,
            schedule_id=uuid4(),
            next_send_at=datetime.now(UTC),
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_instance

        result = get_instance_by_id(mock_session, instance_id)

        self.assertEqual(result, mock_instance)


class TestGetSchedulesToTrigger(unittest.TestCase):
    """Tests for get_schedules_to_trigger operation."""

    def test_returns_active_schedules_due_to_trigger(self) -> None:
        """Test that active schedules past trigger time are returned."""
        mock_session = MagicMock()
        now = datetime.now(UTC)
        mock_schedules = [
            ReminderSchedule(
                id=uuid4(),
                message="Test",
                chat_id=123,
                next_trigger_at=now - timedelta(minutes=5),
                is_active=True,
            )
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_schedules

        result = get_schedules_to_trigger(mock_session, now)

        self.assertEqual(len(result), 1)


class TestGetInstancesToSend(unittest.TestCase):
    """Tests for get_instances_to_send operation."""

    def test_returns_pending_instances_due_to_send(self) -> None:
        """Test that pending instances past send time are returned."""
        mock_session = MagicMock()
        now = datetime.now(UTC)
        mock_instances = [
            ReminderInstance(
                id=uuid4(),
                schedule_id=uuid4(),
                status=ReminderStatus.PENDING.value,
                next_send_at=now - timedelta(minutes=1),
            )
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_instances

        result = get_instances_to_send(mock_session, now)

        self.assertEqual(len(result), 1)


class TestMarkInstanceSent(unittest.TestCase):
    """Tests for mark_instance_sent operation."""

    def test_updates_instance_after_send(self) -> None:
        """Test that instance is updated correctly after sending."""
        mock_session = MagicMock()
        now = datetime.now(UTC)
        instance = ReminderInstance(
            id=uuid4(),
            schedule_id=uuid4(),
            status=ReminderStatus.PENDING.value,
            send_count=0,
            next_send_at=now,
        )

        mark_instance_sent(mock_session, instance, now)

        self.assertEqual(instance.status, ReminderStatus.ACTIVE.value)
        self.assertEqual(instance.send_count, 1)
        self.assertEqual(instance.last_sent_at, now)
        expected_next = now + timedelta(minutes=RESEND_INTERVAL_MINUTES)
        self.assertEqual(instance.next_send_at, expected_next)
        self.assertIsNone(instance.snoozed_until)
        mock_session.flush.assert_called_once()


class TestAcknowledgeInstance(unittest.TestCase):
    """Tests for acknowledge_instance operation."""

    def test_acknowledges_instance(self) -> None:
        """Test that instance is acknowledged correctly."""
        mock_session = MagicMock()
        instance_id = uuid4()
        now = datetime.now(UTC)
        mock_instance = ReminderInstance(
            id=instance_id,
            schedule_id=uuid4(),
            status=ReminderStatus.ACTIVE.value,
            next_send_at=now,
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_instance

        result = acknowledge_instance(mock_session, instance_id, now)

        self.assertEqual(result.status, ReminderStatus.ACKNOWLEDGED.value)
        self.assertEqual(result.acknowledged_at, now)
        mock_session.flush.assert_called_once()

    def test_returns_none_when_not_found(self) -> None:
        """Test that None is returned when instance not found."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = acknowledge_instance(mock_session, uuid4())

        self.assertIsNone(result)


class TestSnoozeInstance(unittest.TestCase):
    """Tests for snooze_instance operation."""

    def test_snoozes_instance(self) -> None:
        """Test that instance is snoozed correctly."""
        mock_session = MagicMock()
        instance_id = uuid4()
        snooze_until = datetime.now(UTC) + timedelta(hours=1)
        mock_instance = ReminderInstance(
            id=instance_id,
            schedule_id=uuid4(),
            status=ReminderStatus.ACTIVE.value,
            next_send_at=datetime.now(UTC),
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_instance

        result = snooze_instance(mock_session, instance_id, snooze_until)

        self.assertEqual(result.status, ReminderStatus.SNOOZED.value)
        self.assertEqual(result.snoozed_until, snooze_until)


class TestExpireInstance(unittest.TestCase):
    """Tests for expire_instance operation."""

    def test_expires_instance(self) -> None:
        """Test that instance is expired correctly."""
        mock_session = MagicMock()
        now = datetime.now(UTC)
        instance = ReminderInstance(
            id=uuid4(),
            schedule_id=uuid4(),
            status=ReminderStatus.ACTIVE.value,
            send_count=3,
            next_send_at=now,
        )

        expire_instance(mock_session, instance, now)

        self.assertEqual(instance.status, ReminderStatus.EXPIRED.value)
        self.assertEqual(instance.expired_at, now)
        mock_session.flush.assert_called_once()


class TestUpdateScheduleNextTrigger(unittest.TestCase):
    """Tests for update_schedule_next_trigger operation."""

    def test_updates_next_trigger(self) -> None:
        """Test that next trigger time is updated."""
        mock_session = MagicMock()
        next_trigger = datetime.now(UTC) + timedelta(days=1)
        schedule = ReminderSchedule(
            id=uuid4(),
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
        )

        update_schedule_next_trigger(mock_session, schedule, next_trigger)

        self.assertEqual(schedule.next_trigger_at, next_trigger)
        mock_session.flush.assert_called_once()


class TestDeactivateSchedule(unittest.TestCase):
    """Tests for deactivate_schedule operation."""

    def test_deactivates_schedule(self) -> None:
        """Test that schedule is deactivated."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
            is_active=True,
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        result = deactivate_schedule(mock_session, schedule_id)

        self.assertFalse(result.is_active)
        mock_session.flush.assert_called_once()

    def test_returns_none_when_not_found(self) -> None:
        """Test that None is returned when schedule not found."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = deactivate_schedule(mock_session, uuid4())

        self.assertIsNone(result)


class TestUpdateReminderSchedule(unittest.TestCase):
    """Tests for update_reminder_schedule operation."""

    def test_updates_message_only(self) -> None:
        """Test updating only the message."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Old message",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
            cron_schedule="0 9 * * 3",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        result = update_reminder_schedule(mock_session, schedule_id, message="New message")

        self.assertEqual(result.message, "New message")
        self.assertEqual(result.cron_schedule, "0 9 * * 3")  # Unchanged
        mock_session.flush.assert_called_once()

    def test_updates_cron_schedule_only(self) -> None:
        """Test updating only the cron schedule."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
            cron_schedule="0 9 * * 3",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        result = update_reminder_schedule(mock_session, schedule_id, cron_schedule="0 9 * * 2")

        self.assertEqual(result.cron_schedule, "0 9 * * 2")
        self.assertEqual(result.message, "Test")  # Unchanged
        mock_session.flush.assert_called_once()

    def test_updates_next_trigger_at_only(self) -> None:
        """Test updating only the trigger time."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        old_trigger = datetime.now(UTC)
        new_trigger = old_trigger + timedelta(days=1)
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123,
            next_trigger_at=old_trigger,
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        result = update_reminder_schedule(mock_session, schedule_id, next_trigger_at=new_trigger)

        self.assertEqual(result.next_trigger_at, new_trigger)
        self.assertEqual(result.message, "Test")  # Unchanged
        mock_session.flush.assert_called_once()

    def test_updates_multiple_fields(self) -> None:
        """Test updating multiple fields at once."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        new_trigger = datetime.now(UTC) + timedelta(days=1)
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Old message",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
            cron_schedule="0 9 * * 3",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        result = update_reminder_schedule(
            mock_session,
            schedule_id,
            message="New message",
            cron_schedule="0 9 * * 2",
            next_trigger_at=new_trigger,
        )

        self.assertEqual(result.message, "New message")
        self.assertEqual(result.cron_schedule, "0 9 * * 2")
        self.assertEqual(result.next_trigger_at, new_trigger)
        mock_session.flush.assert_called_once()

    def test_clears_cron_schedule(self) -> None:
        """Test clearing cron schedule to convert to one-time."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_schedule = ReminderSchedule(
            id=schedule_id,
            message="Test",
            chat_id=123,
            next_trigger_at=datetime.now(UTC),
            cron_schedule="0 9 * * 3",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_schedule

        # Empty string means "clear the cron schedule"
        result = update_reminder_schedule(mock_session, schedule_id, cron_schedule="")

        self.assertIsNone(result.cron_schedule)
        mock_session.flush.assert_called_once()

    def test_returns_none_when_not_found(self) -> None:
        """Test that None is returned when schedule not found."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = update_reminder_schedule(mock_session, uuid4(), message="Test")

        self.assertIsNone(result)


class TestListSchedulesForChat(unittest.TestCase):
    """Tests for list_schedules_for_chat operation."""

    def test_returns_active_schedules_by_default(self) -> None:
        """Test that only active schedules are returned by default."""
        mock_session = MagicMock()
        mock_schedules = [
            ReminderSchedule(
                id=uuid4(),
                message="Test",
                chat_id=123,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
            )
        ]
        mock_query = MagicMock()
        mock_session.query.return_value.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            mock_schedules
        )

        result = list_schedules_for_chat(mock_session, chat_id=123)

        self.assertEqual(len(result), 1)

    def test_returns_all_schedules_when_include_inactive(self) -> None:
        """Test that inactive schedules are included when flag is set."""
        mock_session = MagicMock()
        mock_schedules = [
            ReminderSchedule(
                id=uuid4(),
                message="Active",
                chat_id=123,
                next_trigger_at=datetime.now(UTC),
                is_active=True,
            ),
            ReminderSchedule(
                id=uuid4(),
                message="Inactive",
                chat_id=123,
                next_trigger_at=datetime.now(UTC),
                is_active=False,
            ),
        ]
        mock_query = MagicMock()
        mock_session.query.return_value.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_schedules

        result = list_schedules_for_chat(mock_session, chat_id=123, include_inactive=True)

        self.assertEqual(len(result), 2)


class TestGetActiveInstanceForSchedule(unittest.TestCase):
    """Tests for get_active_instance_for_schedule operation."""

    def test_returns_active_instance(self) -> None:
        """Test that active instance is returned."""
        mock_session = MagicMock()
        schedule_id = uuid4()
        mock_instance = ReminderInstance(
            id=uuid4(),
            schedule_id=schedule_id,
            status=ReminderStatus.ACTIVE.value,
            next_send_at=datetime.now(UTC),
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_instance

        result = get_active_instance_for_schedule(mock_session, schedule_id)

        self.assertEqual(result, mock_instance)

    def test_returns_none_when_no_active_instance(self) -> None:
        """Test that None is returned when no active instance exists."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = get_active_instance_for_schedule(mock_session, uuid4())

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
