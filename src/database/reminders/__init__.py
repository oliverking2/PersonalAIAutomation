"""Database models and operations for user reminders."""

from src.database.reminders.models import (
    ReminderInstance,
    ReminderSchedule,
    ReminderStatus,
)
from src.database.reminders.operations import (
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
    update_schedule_next_trigger,
)

__all__ = [
    # Models
    "ReminderInstance",
    "ReminderSchedule",
    "ReminderStatus",
    # Operations
    "acknowledge_instance",
    "create_reminder_instance",
    "create_reminder_schedule",
    "deactivate_schedule",
    "expire_instance",
    "get_active_instance_for_schedule",
    "get_instance_by_id",
    "get_instances_to_send",
    "get_schedule_by_id",
    "get_schedules_to_trigger",
    "list_schedules_for_chat",
    "mark_instance_sent",
    "snooze_instance",
    "update_schedule_next_trigger",
]
