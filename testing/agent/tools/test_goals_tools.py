"""Tests for goals tool handlers."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.goals import (
    GetGoalArgs,
    UpdateGoalArgs,
    create_goal,
    get_goal,
    get_goals_tools,
    query_goals,
    update_goal,
)
from src.api.notion.goals.models import (
    GoalCreateRequest,
    GoalQueryRequest,
)
from src.notion.enums import GoalStatus, Priority


class TestGoalsToolDefinitions(unittest.TestCase):
    """Tests for goals tool definitions."""

    def test_get_goals_tools_returns_four_tools(self) -> None:
        """Test that get_goals_tools returns all four tools."""
        tools = get_goals_tools()

        self.assertEqual(len(tools), 4)
        tool_names = {t.name for t in tools}
        self.assertEqual(
            tool_names,
            {
                "query_goals",
                "get_goal",
                "create_goal",
                "update_goal",
            },
        )

    def test_query_and_get_are_safe(self) -> None:
        """Test that query and get tools are marked as safe."""
        tools = get_goals_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_goals"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_goal"].risk_level, RiskLevel.SAFE)

    def test_create_and_update_are_sensitive(self) -> None:
        """Test that create and update tools are marked as sensitive."""
        tools = get_goals_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["create_goal"].risk_level, RiskLevel.SENSITIVE)
        self.assertEqual(tool_dict["update_goal"].risk_level, RiskLevel.SENSITIVE)

    def test_tools_have_goals_tag(self) -> None:
        """Test that all tools have the goals tag."""
        tools = get_goals_tools()

        for tool in tools:
            self.assertIn("goals", tool.tags)

    def test_tools_generate_valid_json_schema(self) -> None:
        """Test that all tools generate valid JSON schemas."""
        tools = get_goals_tools()

        for tool in tools:
            schema = tool.to_json_schema()
            self.assertIn("properties", schema)
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")

    def test_descriptions_contain_enum_values(self) -> None:
        """Test that tool descriptions contain dynamic enum values."""
        tools = get_goals_tools()
        tool_dict = {t.name: t for t in tools}

        # Check query_goals contains status options
        query_desc = tool_dict["query_goals"].description
        self.assertIn("Not started", query_desc)
        self.assertIn("In progress", query_desc)
        self.assertIn("Done", query_desc)


class TestGoalQueryRequest(unittest.TestCase):
    """Tests for GoalQueryRequest model (from API)."""

    def test_default_values(self) -> None:
        """Test default argument values."""
        args = GoalQueryRequest()

        self.assertIsNone(args.status)
        self.assertIsNone(args.priority)
        self.assertEqual(args.limit, 50)

    def test_all_filters(self) -> None:
        """Test setting all filter options."""
        args = GoalQueryRequest(
            status=GoalStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            limit=10,
        )

        self.assertEqual(args.status, GoalStatus.IN_PROGRESS)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.limit, 10)


class TestGoalCreateRequest(unittest.TestCase):
    """Tests for GoalCreateRequest model (from API)."""

    def test_minimal_args(self) -> None:
        """Test creating with only required fields."""
        args = GoalCreateRequest(goal_name="Test Goal")

        self.assertEqual(args.goal_name, "Test Goal")
        self.assertEqual(args.status, GoalStatus.NOT_STARTED)
        self.assertIsNone(args.priority)
        self.assertIsNone(args.progress)
        self.assertIsNone(args.due_date)

    def test_full_args(self) -> None:
        """Test creating with all fields."""
        args = GoalCreateRequest(
            goal_name="Important Goal",
            status=GoalStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            progress=50.0,
            due_date=date(2025, 6, 1),
        )

        self.assertEqual(args.goal_name, "Important Goal")
        self.assertEqual(args.status, GoalStatus.IN_PROGRESS)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.progress, 50.0)
        self.assertEqual(args.due_date, date(2025, 6, 1))


class TestUpdateGoalArgs(unittest.TestCase):
    """Tests for UpdateGoalArgs model."""

    def test_minimal_args(self) -> None:
        """Test creating with only goal_id."""
        args = UpdateGoalArgs(goal_id="goal-123")

        self.assertEqual(args.goal_id, "goal-123")
        self.assertIsNone(args.goal_name)
        self.assertIsNone(args.status)

    def test_with_progress(self) -> None:
        """Test update with progress."""
        args = UpdateGoalArgs(
            goal_id="goal-123",
            status=GoalStatus.DONE,
            progress=100.0,
        )

        self.assertEqual(args.status, GoalStatus.DONE)
        self.assertEqual(args.progress, 100.0)


class TestQueryGoalsHandler(unittest.TestCase):
    """Tests for query_goals handler."""

    @patch("src.agent.tools.goals._get_client")
    def test_query_without_filters(self, mock_get_client: MagicMock) -> None:
        """Test querying without any filters."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "goal-1", "goal_name": "Test"}]}

        result = query_goals(GoalQueryRequest())

        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["items"]), 1)
        mock_client.post.assert_called_once_with("/notion/goals/query", json={"limit": 50})

    @patch("src.agent.tools.goals._get_client")
    def test_query_with_status_filter(self, mock_get_client: MagicMock) -> None:
        """Test querying with status filter."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        query_goals(GoalQueryRequest(status=GoalStatus.IN_PROGRESS))

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["status"], "In progress")

    @patch("src.agent.tools.goals._get_client")
    def test_query_with_all_filters(self, mock_get_client: MagicMock) -> None:
        """Test querying with all filters."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        query_goals(
            GoalQueryRequest(
                status=GoalStatus.NOT_STARTED,
                priority=Priority.HIGH,
                limit=5,
            )
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["status"], "Not started")
        self.assertEqual(payload["priority"], "High")
        self.assertEqual(payload["limit"], 5)


class TestGetGoalHandler(unittest.TestCase):
    """Tests for get_goal handler."""

    @patch("src.agent.tools.goals._get_client")
    def test_get_goal(self, mock_get_client: MagicMock) -> None:
        """Test getting a goal."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "goal-123", "goal_name": "Test Goal"}

        result = get_goal(GetGoalArgs(goal_id="goal-123"))

        self.assertEqual(result["item"]["id"], "goal-123")
        self.assertEqual(result["item"]["goal_name"], "Test Goal")
        mock_client.get.assert_called_once_with("/notion/goals/goal-123")


class TestCreateGoalHandler(unittest.TestCase):
    """Tests for create_goal handler."""

    @patch("src.agent.tools.goals._get_client")
    def test_create_goal_minimal(self, mock_get_client: MagicMock) -> None:
        """Test creating a goal with minimal fields."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-goal", "goal_name": "New Goal"}

        result = create_goal(GoalCreateRequest(goal_name="New Goal"))

        self.assertTrue(result["created"])
        self.assertEqual(result["item"]["goal_name"], "New Goal")
        mock_client.post.assert_called_once()

        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/goals")
        payload = call_args[1]["json"]
        self.assertEqual(payload["goal_name"], "New Goal")
        self.assertEqual(payload["status"], "Not started")

    @patch("src.agent.tools.goals._get_client")
    def test_create_goal_full(self, mock_get_client: MagicMock) -> None:
        """Test creating a goal with all fields."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-goal", "goal_name": "Important Goal"}

        result = create_goal(
            GoalCreateRequest(
                goal_name="Important Goal",
                status=GoalStatus.IN_PROGRESS,
                priority=Priority.HIGH,
                progress=25.0,
            )
        )

        self.assertTrue(result["created"])
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["goal_name"], "Important Goal")
        self.assertEqual(payload["status"], "In progress")
        self.assertEqual(payload["priority"], "High")
        self.assertEqual(payload["progress"], 25.0)


class TestUpdateGoalHandler(unittest.TestCase):
    """Tests for update_goal handler."""

    @patch("src.agent.tools.goals._get_client")
    def test_update_goal(self, mock_get_client: MagicMock) -> None:
        """Test updating a goal."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "goal-123", "goal_name": "Updated Goal"}

        result = update_goal(
            UpdateGoalArgs(
                goal_id="goal-123",
                goal_name="Updated Goal",
                status=GoalStatus.DONE,
            )
        )

        self.assertTrue(result["updated"])
        self.assertEqual(result["item"]["goal_name"], "Updated Goal")
        mock_client.patch.assert_called_once()

        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/goals/goal-123")
        payload = call_args[1]["json"]
        self.assertEqual(payload["goal_name"], "Updated Goal")
        self.assertEqual(payload["status"], "Done")
        # goal_id should not be in payload
        self.assertNotIn("goal_id", payload)

    def test_update_no_properties(self) -> None:
        """Test update with no properties returns error."""
        result = update_goal(UpdateGoalArgs(goal_id="goal-123"))

        self.assertFalse(result["updated"])
        self.assertIn("error", result)

    @patch("src.agent.tools.goals._get_client")
    def test_update_with_progress(self, mock_get_client: MagicMock) -> None:
        """Test updating with progress."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "goal-123"}

        update_goal(
            UpdateGoalArgs(
                goal_id="goal-123",
                progress=75.0,
            )
        )

        call_args = mock_client.patch.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["progress"], 75.0)


if __name__ == "__main__":
    unittest.main()
