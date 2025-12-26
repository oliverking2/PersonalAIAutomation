"""Tests for tasks tool handlers."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.tasks import (
    GetTaskArgs,
    UpdateTaskArgs,
    create_task,
    get_task,
    get_tasks_tools,
    query_tasks,
    update_task,
)
from src.api.notion.tasks.models import (
    TaskCreateRequest,
    TaskQueryRequest,
)
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
        """Test that query and get tools are marked as safe."""
        tools = get_tasks_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_tasks"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_task"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["create_task"].risk_level, RiskLevel.SAFE)

    def test_sensitive_tools(self) -> None:
        """Test that create and update tools are marked as sensitive."""
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


class TestUpdateTaskArgs(unittest.TestCase):
    """Tests for UpdateTaskArgs model."""

    def test_minimal_args(self) -> None:
        """Test creating with only task_id."""
        args = UpdateTaskArgs(task_id="task-123")

        self.assertEqual(args.task_id, "task-123")
        self.assertIsNone(args.task_name)
        self.assertIsNone(args.status)

    def test_with_due_date(self) -> None:
        """Test update with due_date."""
        args = UpdateTaskArgs(
            task_id="task-123",
            status=TaskStatus.DONE,
            due_date=date(2025, 1, 15),
        )

        self.assertEqual(args.status, TaskStatus.DONE)
        self.assertEqual(args.due_date, date(2025, 1, 15))


class TestQueryTasksHandler(unittest.TestCase):
    """Tests for query_tasks handler."""

    @patch("src.agent.tools.tasks._get_client")
    def test_query_without_filters(self, mock_get_client: MagicMock) -> None:
        """Test querying without any filters."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "task-1", "task_name": "Test"}]}

        result = query_tasks(TaskQueryRequest())

        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["items"]), 1)
        mock_client.post.assert_called_once_with(
            "/notion/tasks/query", json={"include_done": False, "limit": 50}
        )

    @patch("src.agent.tools.tasks._get_client")
    def test_query_with_status_filter(self, mock_get_client: MagicMock) -> None:
        """Test querying with status filter."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        query_tasks(TaskQueryRequest(status=TaskStatus.IN_PROGRESS))

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["status"], "In progress")

    @patch("src.agent.tools.tasks._get_client")
    def test_query_with_all_filters(self, mock_get_client: MagicMock) -> None:
        """Test querying with all filters."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        query_tasks(
            TaskQueryRequest(
                status=TaskStatus.NOT_STARTED,
                priority=Priority.HIGH,
                effort_level=EffortLevel.MEDIUM,
                task_group=TaskGroup.PERSONAL,
                limit=5,
            )
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["status"], "Not started")
        self.assertEqual(payload["priority"], "High")
        self.assertEqual(payload["effort_level"], "Medium")
        self.assertEqual(payload["task_group"], "Personal")
        self.assertEqual(payload["limit"], 5)


class TestGetTaskHandler(unittest.TestCase):
    """Tests for get_task handler."""

    @patch("src.agent.tools.tasks._get_client")
    def test_get_task(self, mock_get_client: MagicMock) -> None:
        """Test getting a task."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "task-123", "task_name": "Test Task"}

        result = get_task(GetTaskArgs(task_id="task-123"))

        self.assertEqual(result["item"]["id"], "task-123")
        self.assertEqual(result["item"]["task_name"], "Test Task")
        mock_client.get.assert_called_once_with("/notion/tasks/task-123")


class TestCreateTaskHandler(unittest.TestCase):
    """Tests for create_task handler."""

    @patch("src.agent.tools.tasks._get_client")
    def test_create_task_minimal(self, mock_get_client: MagicMock) -> None:
        """Test creating a task with required fields only."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-task", "task_name": "New Task"}

        result = create_task(
            TaskCreateRequest(
                task_name="New Task",
                due_date=date(2025, 6, 1),
                task_group=TaskGroup.PERSONAL,
            )
        )

        self.assertTrue(result["created"])
        self.assertEqual(result["item"]["task_name"], "New Task")
        mock_client.post.assert_called_once()

        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/tasks")
        payload = call_args[1]["json"]
        self.assertEqual(payload["task_name"], "New Task")
        self.assertEqual(payload["status"], "Not started")
        self.assertEqual(payload["priority"], "Low")
        self.assertEqual(payload["effort_level"], "Small")
        self.assertEqual(payload["task_group"], "Personal")
        self.assertEqual(payload["due_date"], "2025-06-01")

    @patch("src.agent.tools.tasks._get_client")
    def test_create_task_full(self, mock_get_client: MagicMock) -> None:
        """Test creating a task with all fields."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-task", "task_name": "Important Task"}

        result = create_task(
            TaskCreateRequest(
                task_name="Important Task",
                status=TaskStatus.IN_PROGRESS,
                priority=Priority.HIGH,
                effort_level=EffortLevel.LARGE,
                task_group=TaskGroup.WORK,
                due_date=date(2025, 7, 15),
            )
        )

        self.assertTrue(result["created"])
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["task_name"], "Important Task")
        self.assertEqual(payload["status"], "In progress")
        self.assertEqual(payload["priority"], "High")
        self.assertEqual(payload["effort_level"], "Large")
        self.assertEqual(payload["task_group"], "Work")
        self.assertEqual(payload["due_date"], "2025-07-15")


class TestUpdateTaskHandler(unittest.TestCase):
    """Tests for update_task handler."""

    @patch("src.agent.tools.tasks._get_client")
    def test_update_task(self, mock_get_client: MagicMock) -> None:
        """Test updating a task."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "task-123", "task_name": "Updated Task"}

        result = update_task(
            UpdateTaskArgs(
                task_id="task-123",
                task_name="Updated Task",
                status=TaskStatus.DONE,
            )
        )

        self.assertTrue(result["updated"])
        self.assertEqual(result["item"]["task_name"], "Updated Task")
        mock_client.patch.assert_called_once()

        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/tasks/task-123")
        payload = call_args[1]["json"]
        self.assertEqual(payload["task_name"], "Updated Task")
        self.assertEqual(payload["status"], "Done")
        # task_id should not be in payload
        self.assertNotIn("task_id", payload)

    def test_update_no_properties(self) -> None:
        """Test update with no properties returns error."""
        result = update_task(UpdateTaskArgs(task_id="task-123"))

        self.assertFalse(result["updated"])
        self.assertIn("error", result)

    @patch("src.agent.tools.tasks._get_client")
    def test_update_with_due_date(self, mock_get_client: MagicMock) -> None:
        """Test updating with due date."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "task-123"}

        update_task(
            UpdateTaskArgs(
                task_id="task-123",
                due_date=date(2025, 1, 15),
            )
        )

        call_args = mock_client.patch.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["due_date"], "2025-01-15")


if __name__ == "__main__":
    unittest.main()
