"""Tests for agent action formatting utilities."""

import unittest

from src.agent.models import PendingToolAction
from src.agent.utils.formatting import (
    format_action,
    format_confirmation_message,
    format_date_human,
    format_datetime_human,
    format_time_human,
)


class TestFormatDateHuman(unittest.TestCase):
    """Tests for format_date_human function."""

    def test_date_only(self) -> None:
        """Test formatting a date-only string."""
        result = format_date_human("2025-01-15")
        self.assertEqual(result, "15th Jan 2025")

    def test_datetime_string(self) -> None:
        """Test formatting a datetime string."""
        result = format_date_human("2025-01-15T14:30:00")
        self.assertEqual(result, "15th Jan 2025")

    def test_datetime_with_timezone(self) -> None:
        """Test formatting a datetime with timezone."""
        result = format_date_human("2025-01-15T14:30:00Z")
        self.assertEqual(result, "15th Jan 2025")

    def test_invalid_date_returns_original(self) -> None:
        """Test that invalid dates are returned as-is."""
        result = format_date_human("not a date")
        self.assertEqual(result, "not a date")

    def test_ordinal_first(self) -> None:
        """Test 1st ordinal suffix."""
        result = format_date_human("2025-01-01")
        self.assertEqual(result, "1st Jan 2025")

    def test_ordinal_second(self) -> None:
        """Test 2nd ordinal suffix."""
        result = format_date_human("2025-01-02")
        self.assertEqual(result, "2nd Jan 2025")

    def test_ordinal_third(self) -> None:
        """Test 3rd ordinal suffix."""
        result = format_date_human("2025-01-03")
        self.assertEqual(result, "3rd Jan 2025")

    def test_ordinal_eleventh(self) -> None:
        """Test 11th ordinal suffix (special case)."""
        result = format_date_human("2025-01-11")
        self.assertEqual(result, "11th Jan 2025")

    def test_ordinal_twenty_first(self) -> None:
        """Test 21st ordinal suffix."""
        result = format_date_human("2025-01-21")
        self.assertEqual(result, "21st Jan 2025")


class TestFormatTimeHuman(unittest.TestCase):
    """Tests for format_time_human function."""

    def test_time_only(self) -> None:
        """Test formatting a time-only string."""
        result = format_time_human("14:30")
        self.assertEqual(result, "2:30 PM")

    def test_morning_time(self) -> None:
        """Test formatting a morning time."""
        result = format_time_human("09:15")
        self.assertEqual(result, "9:15 AM")

    def test_datetime_string(self) -> None:
        """Test formatting time from a datetime string."""
        result = format_time_human("2025-01-15T14:30:00Z")
        self.assertEqual(result, "2:30 PM")

    def test_invalid_time_returns_original(self) -> None:
        """Test that invalid times are returned as-is."""
        result = format_time_human("not a time")
        self.assertEqual(result, "not a time")


class TestFormatDatetimeHuman(unittest.TestCase):
    """Tests for format_datetime_human function."""

    def test_datetime_string(self) -> None:
        """Test formatting a full datetime string."""
        result = format_datetime_human("2025-01-15T14:30:00Z")
        self.assertEqual(result, "15th Jan 2025 at 2:30 PM")

    def test_invalid_datetime_returns_original(self) -> None:
        """Test that invalid datetimes are returned as-is."""
        result = format_datetime_human("not a datetime")
        self.assertEqual(result, "not a datetime")


class TestFormatAction(unittest.TestCase):
    """Tests for format_action function."""

    def test_update_due_date_with_entity(self) -> None:
        """Test formatting an update with due_date field."""
        result = format_action(
            "update_task",
            "Review quarterly report",
            {"task_id": "abc-123", "due_date": "2025-01-15"},
        )
        self.assertEqual(
            result,
            'update the due date for "Review quarterly report" to 15th Jan 2025',
        )

    def test_update_status_with_entity(self) -> None:
        """Test formatting an update with status field."""
        result = format_action(
            "update_goal",
            "Learn Spanish",
            {"goal_id": "def-456", "status": "In Progress"},
        )
        self.assertEqual(result, 'mark "Learn Spanish" as In Progress')

    def test_update_priority_with_entity(self) -> None:
        """Test formatting an update with priority field."""
        result = format_action(
            "update_task",
            "Important task",
            {"task_id": "abc-123", "priority": "High"},
        )
        self.assertEqual(result, 'change the priority of "Important task" to High')

    def test_update_multiple_fields(self) -> None:
        """Test formatting an update with multiple fields."""
        result = format_action(
            "update_task",
            "My task",
            {"task_id": "abc-123", "status": "Done", "priority": "Low"},
        )
        self.assertIn('update "My task"', result)
        self.assertIn("status: Done", result)
        self.assertIn("priority: Low", result)

    def test_update_without_entity_name(self) -> None:
        """Test formatting an update without entity name."""
        result = format_action(
            "update_reminder",
            None,
            {"reminder_id": "rem-123", "message": "New message"},
        )
        self.assertIn("update", result)
        self.assertIn("New message", result)

    def test_cancel_reminder_with_entity(self) -> None:
        """Test formatting a cancel action with entity name."""
        result = format_action(
            "cancel_reminder",
            "Take vitamins",
            {"reminder_id": "rem-123"},
        )
        self.assertEqual(result, 'cancel the reminder "Take vitamins"')

    def test_cancel_reminder_without_entity(self) -> None:
        """Test formatting a cancel action without entity name."""
        result = format_action(
            "cancel_reminder",
            None,
            {"reminder_id": "abc12345-6789"},
        )
        self.assertIn("cancel reminder", result)
        self.assertIn("abc12345", result)

    def test_unknown_tool_with_entity(self) -> None:
        """Test formatting an unknown tool type with entity name."""
        result = format_action(
            "unknown_tool",
            "Some entity",
            {"some_arg": "value"},
        )
        self.assertEqual(result, 'unknown tool "Some entity"')

    def test_unknown_tool_without_entity(self) -> None:
        """Test formatting an unknown tool type without entity name."""
        result = format_action(
            "unknown_tool",
            None,
            {"some_arg": "value"},
        )
        self.assertEqual(result, "unknown tool")

    def test_update_content_only(self) -> None:
        """Test formatting a content-only update."""
        result = format_action(
            "update_task",
            "My task",
            {"task_id": "abc-123", "content": "## Description\n\nSome text here"},
        )
        self.assertEqual(result, 'update the description for "My task"')

    def test_update_long_content_truncated(self) -> None:
        """Test that long content is truncated in multi-field updates."""
        long_content = "## Description\n\n" + "A" * 100
        result = format_action(
            "update_task",
            "My task",
            {"task_id": "abc-123", "content": long_content, "status": "Done"},
        )
        self.assertIn('update "My task"', result)
        self.assertIn("status: Done", result)
        self.assertIn("content:", result)
        self.assertIn("...", result)
        # Full content should not appear
        self.assertNotIn("A" * 100, result)

    def test_update_project_id_only_link(self) -> None:
        """Test formatting when only project_id is set (linking to project)."""
        result = format_action(
            "update_task",
            "My task",
            {"task_id": "abc-123", "project_id": "project-456"},
        )
        self.assertEqual(result, 'link "My task" to a project')

    def test_update_project_id_only_unlink(self) -> None:
        """Test formatting when project_id is cleared (unlinking from project)."""
        result = format_action(
            "update_task",
            "My task",
            {"task_id": "abc-123", "project_id": None},
        )
        self.assertEqual(result, 'unlink "My task" from its project')

    def test_update_project_id_with_other_fields(self) -> None:
        """Test formatting when project_id is set with other fields."""
        result = format_action(
            "update_task",
            "My task",
            {"task_id": "abc-123", "project_id": "project-456", "status": "In Progress"},
        )
        self.assertIn('update "My task"', result)
        self.assertIn("status: In Progress", result)
        self.assertIn("link to project", result)

    def test_update_project_id_without_entity_name(self) -> None:
        """Test formatting project link without entity name."""
        result = format_action(
            "update_task",
            None,
            {"task_id": "abc-123", "project_id": "project-456"},
        )
        self.assertEqual(result, "link to a project")


class TestFormatConfirmationMessage(unittest.TestCase):
    """Tests for format_confirmation_message function."""

    def _make_tool(
        self,
        index: int,
        tool_name: str,
        input_args: dict,
        previous_values: dict | None = None,
    ) -> PendingToolAction:
        """Create a PendingToolAction for testing."""
        return PendingToolAction(
            index=index,
            tool_use_id=f"tool-{index}",
            tool_name=tool_name,
            tool_description=f"Description for {tool_name}",
            input_args=input_args,
            action_summary=f"Summary for {tool_name}",
            previous_values=previous_values or {},
        )

    def test_single_action(self) -> None:
        """Test formatting a single action confirmation."""
        tool = self._make_tool(
            1,
            "update_task",
            {"task_id": "abc-123", "due_date": "2025-01-15"},
        )
        result = format_confirmation_message([(tool, "Review quarterly report")])

        self.assertIn("I'll", result)
        self.assertIn("update the due date", result)
        self.assertIn("Review quarterly report", result)
        self.assertIn("15th Jan 2025", result)
        self.assertIn("sound good?", result)

    def test_multiple_actions(self) -> None:
        """Test formatting multiple action confirmations."""
        tool1 = self._make_tool(
            1,
            "update_task",
            {"task_id": "abc-123", "due_date": "2025-01-15"},
        )
        tool2 = self._make_tool(
            2,
            "update_goal",
            {"goal_id": "def-456", "status": "In Progress"},
        )
        result = format_confirmation_message(
            [
                (tool1, "Review quarterly report"),
                (tool2, "Learn Spanish"),
            ]
        )

        self.assertIn("Just confirming these:", result)
        self.assertIn("1.", result)
        self.assertIn("2.", result)
        self.assertIn("Update the due date", result)  # Capitalised
        self.assertIn("Mark", result)  # Capitalised
        self.assertNotIn("sound good?", result)

    def test_single_action_cancel(self) -> None:
        """Test formatting a single cancel action."""
        tool = self._make_tool(
            1,
            "cancel_reminder",
            {"reminder_id": "rem-123"},
        )
        result = format_confirmation_message([(tool, "Take vitamins")])

        self.assertIn("I'll", result)
        self.assertIn('cancel the reminder "Take vitamins"', result)
        self.assertIn("sound good?", result)

    def test_action_without_entity_name(self) -> None:
        """Test formatting when entity name is None."""
        tool = self._make_tool(
            1,
            "update_reminder",
            {"reminder_id": "rem-123", "message": "New message"},
        )
        result = format_confirmation_message([(tool, None)])

        self.assertIn("I'll", result)
        self.assertIn("update", result)
        self.assertIn("sound good?", result)

    def test_single_action_with_content_diff(self) -> None:
        """Test confirmation message shows diff for content updates."""
        tool = self._make_tool(
            1,
            "update_task",
            {"task_id": "abc-123", "content": "New content"},
            previous_values={"content": "Old content"},
        )
        result = format_confirmation_message([(tool, "Test Task")])

        self.assertIn("I'd", result)
        self.assertIn('**Before:** "Old content"', result)
        self.assertIn('**After:** "New content"', result)
        self.assertIn("This look right?", result)

    def test_single_action_with_diff_no_old_content(self) -> None:
        """Test diff display when old content is None."""
        tool = self._make_tool(
            1,
            "update_task",
            {"task_id": "abc-123", "content": "New content"},
        )
        result = format_confirmation_message([(tool, "Test Task")])

        self.assertIn("**Before:** (not available)", result)
        self.assertIn('**After:** "New content"', result)

    def test_batch_actions_with_content_diffs(self) -> None:
        """Test batch confirmation shows inline diffs."""
        tool1 = self._make_tool(
            1,
            "update_task",
            {"task_id": "abc-123", "content": "Updated content 1"},
            previous_values={"content": "Old content 1"},
        )

        tool2 = self._make_tool(
            2,
            "update_task",
            {"task_id": "def-456", "content": "Updated content 2"},
            previous_values={"content": "Old content 2"},
        )

        result = format_confirmation_message(
            [
                (tool1, "Task 1"),
                (tool2, "Task 2"),
            ]
        )

        self.assertIn("Just confirming these:", result)
        self.assertIn("1.", result)
        self.assertIn("2.", result)
        self.assertIn('**Before:** "Old content 1"', result)
        self.assertIn('**After:** "Updated content 1"', result)
        self.assertIn('**Before:** "Old content 2"', result)
        self.assertIn('**After:** "Updated content 2"', result)


if __name__ == "__main__":
    unittest.main()
