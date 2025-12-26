"""Tests for tasks tool definitions."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.tasks import TASK_TOOL_CONFIG, get_tasks_tools
from src.api.notion.tasks.models import TaskCreateRequest, TaskQueryRequest
from src.notion.enums import EffortLevel, Priority, TaskGroup, TaskStatus


class TestTasksToolDefinitions(unittest.TestCase):
    """Tests for tasks tool definitions."""

    def test_get_tasks_tools_returns_four_tools(self) -> None:
        """Test that get_tasks_tools returns all four tools."""
        tools = get_tasks_tools()

        self.assertEqual(len(tools), 4)
        tool_names = {t.name for t in tools}
        self.assertEqual(
            tool_names,
            {
                "query_tasks",
                "get_task",
                "create_task",
                "update_task",
            },
        )

    def test_safe_tools(self) -> None:
        """Test that query, get, and create tools are marked as safe."""
        tools = get_tasks_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_tasks"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_task"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["create_task"].risk_level, RiskLevel.SAFE)

    def test_sensitive_tools(self) -> None:
        """Test that update tool is marked as sensitive."""
        tools = get_tasks_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["update_task"].risk_level, RiskLevel.SENSITIVE)

    def test_tools_have_tasks_tag(self) -> None:
        """Test that all tools have the tasks tag."""
        tools = get_tasks_tools()

        for tool in tools:
            self.assertIn("tasks", tool.tags)

    def test_tools_generate_valid_json_schema(self) -> None:
        """Test that all tools generate valid JSON schemas."""
        tools = get_tasks_tools()

        for tool in tools:
            schema = tool.to_json_schema()
            self.assertIn("properties", schema)
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")

    def test_descriptions_contain_enum_values(self) -> None:
        """Test that tool descriptions contain dynamic enum values."""
        tools = get_tasks_tools()
        tool_dict = {t.name: t for t in tools}

        # Check query_tasks contains status options
        query_desc = tool_dict["query_tasks"].description
        self.assertIn("Not started", query_desc)
        self.assertIn("In progress", query_desc)
        self.assertIn("Done", query_desc)

        # Check contains effort level options
        self.assertIn("Small", query_desc)
        self.assertIn("Medium", query_desc)
        self.assertIn("Large", query_desc)


class TestTaskToolConfig(unittest.TestCase):
    """Tests for TASK_TOOL_CONFIG."""

    def test_config_domain(self) -> None:
        """Test config has correct domain settings."""
        self.assertEqual(TASK_TOOL_CONFIG.domain, "task")
        self.assertEqual(TASK_TOOL_CONFIG.domain_plural, "tasks")
        self.assertEqual(TASK_TOOL_CONFIG.endpoint_prefix, "/notion/tasks")
        self.assertEqual(TASK_TOOL_CONFIG.id_field, "task_id")

    def test_config_enum_fields(self) -> None:
        """Test config has correct enum fields."""
        self.assertIn("status", TASK_TOOL_CONFIG.enum_fields)
        self.assertIn("priority", TASK_TOOL_CONFIG.enum_fields)
        self.assertIn("effort", TASK_TOOL_CONFIG.enum_fields)
        self.assertIn("group", TASK_TOOL_CONFIG.enum_fields)


class TestTaskQueryRequest(unittest.TestCase):
    """Tests for TaskQueryRequest model (from API)."""

    def test_default_values(self) -> None:
        """Test default argument values."""
        args = TaskQueryRequest()

        self.assertIsNone(args.status)
        self.assertIsNone(args.priority)
        self.assertIsNone(args.effort_level)
        self.assertIsNone(args.task_group)
        self.assertEqual(args.limit, 50)

    def test_all_filters(self) -> None:
        """Test setting all filter options."""
        args = TaskQueryRequest(
            status=TaskStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            effort_level=EffortLevel.LARGE,
            task_group=TaskGroup.WORK,
            limit=10,
        )

        self.assertEqual(args.status, TaskStatus.IN_PROGRESS)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.effort_level, EffortLevel.LARGE)
        self.assertEqual(args.task_group, TaskGroup.WORK)
        self.assertEqual(args.limit, 10)


class TestTaskCreateRequest(unittest.TestCase):
    """Tests for TaskCreateRequest model (from API)."""

    def test_minimal_args(self) -> None:
        """Test creating with only required fields."""
        args = TaskCreateRequest(
            task_name="Test Task",
            due_date=date(2025, 6, 1),
            task_group=TaskGroup.PERSONAL,
        )

        self.assertEqual(args.task_name, "Test Task")
        self.assertEqual(args.status, TaskStatus.NOT_STARTED)
        self.assertEqual(args.priority, Priority.LOW)
        self.assertEqual(args.effort_level, EffortLevel.SMALL)
        self.assertEqual(args.task_group, TaskGroup.PERSONAL)
        self.assertEqual(args.due_date, date(2025, 6, 1))

    def test_full_args(self) -> None:
        """Test creating with all fields."""
        args = TaskCreateRequest(
            task_name="Important Task",
            status=TaskStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            effort_level=EffortLevel.LARGE,
            task_group=TaskGroup.WORK,
            due_date=date(2025, 6, 1),
        )

        self.assertEqual(args.task_name, "Important Task")
        self.assertEqual(args.status, TaskStatus.IN_PROGRESS)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.effort_level, EffortLevel.LARGE)
        self.assertEqual(args.task_group, TaskGroup.WORK)
        self.assertEqual(args.due_date, date(2025, 6, 1))


class TestTaskToolHandlers(unittest.TestCase):
    """Tests for task tool handlers."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = get_tasks_tools()
        self.tool_dict = {t.name: t for t in self.tools}

    @patch("src.agent.tools.factory._get_client")
    def test_query_handler(self, mock_get_client: MagicMock) -> None:
        """Test query_tasks handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "task-1"}]}

        tool = self.tool_dict["query_tasks"]
        args = TaskQueryRequest(status=TaskStatus.IN_PROGRESS)
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/tasks/query")
        self.assertEqual(result["count"], 1)

    @patch("src.agent.tools.factory._get_client")
    def test_get_handler(self, mock_get_client: MagicMock) -> None:
        """Test get_task handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "task-123", "task_name": "Test"}

        tool = self.tool_dict["get_task"]
        args = tool.args_model(task_id="task-123")
        result = tool.handler(args)

        mock_client.get.assert_called_once_with("/notion/tasks/task-123")
        self.assertEqual(result["item"]["id"], "task-123")

    @patch("src.agent.tools.factory._get_client")
    def test_create_handler(self, mock_get_client: MagicMock) -> None:
        """Test create_task handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-task", "task_name": "New Task"}

        tool = self.tool_dict["create_task"]
        args = TaskCreateRequest(
            task_name="New Task",
            due_date=date(2025, 6, 1),
            task_group=TaskGroup.PERSONAL,
        )
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/tasks")
        self.assertTrue(result["created"])

    @patch("src.agent.tools.factory._get_client")
    def test_update_handler(self, mock_get_client: MagicMock) -> None:
        """Test update_task handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "task-123", "task_name": "Updated"}

        tool = self.tool_dict["update_task"]
        args = tool.args_model(task_id="task-123", task_name="Updated")
        result = tool.handler(args)

        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/tasks/task-123")
        # task_id should not be in payload
        payload = call_args[1]["json"]
        self.assertNotIn("task_id", payload)
        self.assertTrue(result["updated"])

    def test_update_no_properties_error(self) -> None:
        """Test update with no properties returns error."""
        tool = self.tool_dict["update_task"]
        args = tool.args_model(task_id="task-123")
        result = tool.handler(args)

        self.assertFalse(result["updated"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
