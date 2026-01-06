"""Tests for reminders tool definitions."""

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.reminders import (
    CANCEL_REMINDER_TOOL,
    CREATE_REMINDER_TOOL,
    QUERY_REMINDERS_TOOL,
    CancelReminderArgs,
    CreateReminderArgs,
    QueryRemindersArgs,
    get_reminders_tools,
)


class TestRemindersToolDefinitions(unittest.TestCase):
    """Tests for reminders tool definitions."""

    def test_get_reminders_tools_returns_three_tools(self) -> None:
        """Test that get_reminders_tools returns all three tools."""
        tools = get_reminders_tools()

        self.assertEqual(len(tools), 3)
        tool_names = {t.name for t in tools}
        self.assertEqual(
            tool_names,
            {
                "create_reminder",
                "query_reminders",
                "cancel_reminder",
            },
        )

    def test_safe_tools(self) -> None:
        """Test that create and query tools are marked as safe."""
        tools = get_reminders_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["create_reminder"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["query_reminders"].risk_level, RiskLevel.SAFE)

    def test_sensitive_tools(self) -> None:
        """Test that cancel tool is marked as sensitive."""
        tools = get_reminders_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["cancel_reminder"].risk_level, RiskLevel.SENSITIVE)

    def test_tools_have_reminders_tag(self) -> None:
        """Test that all tools have the reminders tag."""
        tools = get_reminders_tools()

        for tool in tools:
            self.assertIn("reminders", tool.tags)

    def test_tools_generate_valid_json_schema(self) -> None:
        """Test that all tools generate valid JSON schemas."""
        tools = get_reminders_tools()

        for tool in tools:
            schema = tool.to_json_schema()
            self.assertIn("properties", schema)
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")


class TestCreateReminderArgs(unittest.TestCase):
    """Tests for CreateReminderArgs model."""

    def test_required_fields(self) -> None:
        """Test creating with required fields."""
        trigger_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        args = CreateReminderArgs(
            message="Take medication",
            trigger_at=trigger_at,
        )

        self.assertEqual(args.message, "Take medication")
        self.assertEqual(args.trigger_at, trigger_at)
        self.assertIsNone(args.cron_schedule)

    def test_recurring_reminder(self) -> None:
        """Test creating a recurring reminder."""
        trigger_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        args = CreateReminderArgs(
            message="Daily standup",
            trigger_at=trigger_at,
            cron_schedule="0 9 * * 1-5",
        )

        self.assertEqual(args.message, "Daily standup")
        self.assertEqual(args.cron_schedule, "0 9 * * 1-5")

    def test_message_max_length(self) -> None:
        """Test that message has max length constraint."""
        # Should work with 500 chars
        trigger_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        long_message = "x" * 500
        args = CreateReminderArgs(message=long_message, trigger_at=trigger_at)
        self.assertEqual(len(args.message), 500)

        # Should fail with 501 chars
        with self.assertRaises(ValueError):
            CreateReminderArgs(message="x" * 501, trigger_at=trigger_at)


class TestQueryRemindersArgs(unittest.TestCase):
    """Tests for QueryRemindersArgs model."""

    def test_default_values(self) -> None:
        """Test default argument values."""
        args = QueryRemindersArgs()

        self.assertFalse(args.include_inactive)
        self.assertEqual(args.limit, 20)

    def test_custom_values(self) -> None:
        """Test setting custom values."""
        args = QueryRemindersArgs(
            include_inactive=True,
            limit=50,
        )

        self.assertTrue(args.include_inactive)
        self.assertEqual(args.limit, 50)

    def test_limit_constraints(self) -> None:
        """Test limit has min/max constraints."""
        # Min is 1
        with self.assertRaises(ValueError):
            QueryRemindersArgs(limit=0)

        # Max is 100
        with self.assertRaises(ValueError):
            QueryRemindersArgs(limit=101)


class TestCancelReminderArgs(unittest.TestCase):
    """Tests for CancelReminderArgs model."""

    def test_required_fields(self) -> None:
        """Test creating with required fields."""
        args = CancelReminderArgs(reminder_id="abc-123")

        self.assertEqual(args.reminder_id, "abc-123")

    def test_empty_id_rejected(self) -> None:
        """Test that empty reminder_id is rejected."""
        with self.assertRaises(ValueError):
            CancelReminderArgs(reminder_id="")


class TestRemindersToolHandlers(unittest.TestCase):
    """Tests for reminders tool handlers."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = get_reminders_tools()
        self.tool_dict = {t.name: t for t in self.tools}

    @patch("src.agent.tools.reminders._get_client")
    def test_create_handler(self, mock_get_client: MagicMock) -> None:
        """Test create_reminder handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "id": "reminder-123",
            "message": "Test reminder",
            "next_trigger_at": "2024-01-15T09:00:00Z",
            "is_recurring": False,
        }

        tool = self.tool_dict["create_reminder"]
        trigger_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        args = CreateReminderArgs(message="Test reminder", trigger_at=trigger_at)
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/reminders")
        self.assertTrue(result["created"])
        self.assertEqual(result["id"], "reminder-123")

    @patch("src.agent.tools.reminders._get_client")
    def test_create_recurring_handler(self, mock_get_client: MagicMock) -> None:
        """Test create_reminder handler with recurring reminder."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "id": "reminder-456",
            "message": "Daily standup",
            "next_trigger_at": "2024-01-15T09:00:00Z",
            "is_recurring": True,
        }

        tool = self.tool_dict["create_reminder"]
        trigger_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        args = CreateReminderArgs(
            message="Daily standup",
            trigger_at=trigger_at,
            cron_schedule="0 9 * * 1-5",
        )
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["cron_schedule"], "0 9 * * 1-5")
        self.assertTrue(result["is_recurring"])

    @patch("src.agent.tools.reminders._get_client")
    def test_query_handler(self, mock_get_client: MagicMock) -> None:
        """Test query_reminders handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "results": [
                {
                    "id": "reminder-1",
                    "message": "Reminder 1",
                    "next_trigger_at": "2024-01-15T09:00:00Z",
                    "is_recurring": False,
                    "is_active": True,
                    "chat_id": 12345,
                    "created_at": "2024-01-10T08:00:00Z",
                },
                {
                    "id": "reminder-2",
                    "message": "Reminder 2",
                    "next_trigger_at": "2024-01-16T09:00:00Z",
                    "is_recurring": True,
                    "is_active": True,
                    "chat_id": 12345,
                    "created_at": "2024-01-11T08:00:00Z",
                },
            ]
        }

        tool = self.tool_dict["query_reminders"]
        args = QueryRemindersArgs()
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/reminders/query")
        self.assertEqual(result["count"], 2)
        # Verify response is filtered to essential fields
        reminder = result["reminders"][0]
        self.assertIn("id", reminder)
        self.assertIn("message", reminder)
        self.assertNotIn("chat_id", reminder)  # Should be filtered out
        self.assertNotIn("created_at", reminder)  # Should be filtered out

    @patch("src.agent.tools.reminders._get_client")
    def test_query_handler_with_include_inactive(self, mock_get_client: MagicMock) -> None:
        """Test query_reminders handler with include_inactive flag."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        tool = self.tool_dict["query_reminders"]
        args = QueryRemindersArgs(include_inactive=True, limit=10)
        tool.handler(args)

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertTrue(payload["include_inactive"])
        self.assertEqual(payload["limit"], 10)

    @patch("src.agent.tools.reminders._get_client")
    def test_cancel_handler(self, mock_get_client: MagicMock) -> None:
        """Test cancel_reminder handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.delete.return_value = None

        tool = self.tool_dict["cancel_reminder"]
        args = CancelReminderArgs(reminder_id="reminder-123")
        result = tool.handler(args)

        mock_client.delete.assert_called_once_with("/reminders/reminder-123")
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["reminder_id"], "reminder-123")


class TestToolDefinitionDetails(unittest.TestCase):
    """Tests for tool definition details."""

    def test_create_reminder_tool_definition(self) -> None:
        """Test create_reminder tool has correct definition."""
        self.assertEqual(CREATE_REMINDER_TOOL.name, "create_reminder")
        self.assertEqual(CREATE_REMINDER_TOOL.args_model, CreateReminderArgs)
        self.assertIn("Telegram", CREATE_REMINDER_TOOL.description)
        self.assertIn("cron_schedule", CREATE_REMINDER_TOOL.description)

    def test_query_reminders_tool_definition(self) -> None:
        """Test query_reminders tool has correct definition."""
        self.assertEqual(QUERY_REMINDERS_TOOL.name, "query_reminders")
        self.assertEqual(QUERY_REMINDERS_TOOL.args_model, QueryRemindersArgs)
        self.assertIn("active", QUERY_REMINDERS_TOOL.description)

    def test_cancel_reminder_tool_definition(self) -> None:
        """Test cancel_reminder tool has correct definition."""
        self.assertEqual(CANCEL_REMINDER_TOOL.name, "cancel_reminder")
        self.assertEqual(CANCEL_REMINDER_TOOL.args_model, CancelReminderArgs)
        self.assertIn("delete", CANCEL_REMINDER_TOOL.description)
        self.assertIn("remove", CANCEL_REMINDER_TOOL.description)


if __name__ == "__main__":
    unittest.main()
