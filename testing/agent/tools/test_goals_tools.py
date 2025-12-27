"""Tests for goals tool definitions."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.goals import GOAL_TOOL_CONFIG, get_goals_tools
from src.agent.tools.models import AgentGoalCreateArgs
from src.api.notion.goals.models import GoalQueryRequest
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
                "create_goals",
                "update_goal",
            },
        )

    def test_safe_tools(self) -> None:
        """Test that query, get, and create tools are marked as safe."""
        tools = get_goals_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_goals"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_goal"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["create_goals"].risk_level, RiskLevel.SAFE)

    def test_sensitive_tools(self) -> None:
        """Test that update tool is marked as sensitive."""
        tools = get_goals_tools()
        tool_dict = {t.name: t for t in tools}

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


class TestGoalToolConfig(unittest.TestCase):
    """Tests for GOAL_TOOL_CONFIG."""

    def test_config_domain(self) -> None:
        """Test config has correct domain settings."""
        self.assertEqual(GOAL_TOOL_CONFIG.domain, "goal")
        self.assertEqual(GOAL_TOOL_CONFIG.domain_plural, "goals")
        self.assertEqual(GOAL_TOOL_CONFIG.endpoint_prefix, "/notion/goals")
        self.assertEqual(GOAL_TOOL_CONFIG.id_field, "goal_id")

    def test_config_enum_fields(self) -> None:
        """Test config has correct enum fields."""
        self.assertIn("status", GOAL_TOOL_CONFIG.enum_fields)
        self.assertIn("priority", GOAL_TOOL_CONFIG.enum_fields)


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


class TestAgentGoalCreateArgs(unittest.TestCase):
    """Tests for AgentGoalCreateArgs model."""

    def test_minimal_args(self) -> None:
        """Test creating with only required fields."""
        args = AgentGoalCreateArgs(goal_name="Test Goal")

        self.assertEqual(args.goal_name, "Test Goal")
        self.assertEqual(args.status, GoalStatus.NOT_STARTED)
        self.assertEqual(args.priority, Priority.LOW)
        self.assertEqual(args.progress, 0)
        self.assertIsNone(args.due_date)
        self.assertIsNone(args.description)

    def test_full_args(self) -> None:
        """Test creating with all fields."""
        args = AgentGoalCreateArgs(
            goal_name="Important Goal",
            description="What this goal aims to achieve",
            notes="Milestones and references",
            status=GoalStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            progress=50,
            due_date=date(2025, 6, 1),
        )

        self.assertEqual(args.goal_name, "Important Goal")
        self.assertEqual(args.description, "What this goal aims to achieve")
        self.assertEqual(args.notes, "Milestones and references")
        self.assertEqual(args.status, GoalStatus.IN_PROGRESS)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.progress, 50)
        self.assertEqual(args.due_date, date(2025, 6, 1))


class TestGoalToolHandlers(unittest.TestCase):
    """Tests for goal tool handlers."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = get_goals_tools()
        self.tool_dict = {t.name: t for t in self.tools}

    @patch("src.agent.tools.factory._get_client")
    def test_query_handler(self, mock_get_client: MagicMock) -> None:
        """Test query_goals handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "goal-1"}]}

        tool = self.tool_dict["query_goals"]
        args = GoalQueryRequest(status=GoalStatus.IN_PROGRESS)
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/goals/query")
        self.assertEqual(result["count"], 1)

    @patch("src.agent.tools.factory._get_client")
    def test_get_handler(self, mock_get_client: MagicMock) -> None:
        """Test get_goal handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "goal-123", "goal_name": "Test"}

        tool = self.tool_dict["get_goal"]
        args = tool.args_model(goal_id="goal-123")
        result = tool.handler(args)

        mock_client.get.assert_called_once_with("/notion/goals/goal-123")
        self.assertEqual(result["item"]["id"], "goal-123")

    @patch("src.agent.tools.factory._get_client")
    def test_create_handler(self, mock_get_client: MagicMock) -> None:
        """Test create_goal handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        goal_name = "Run a half marathon by June"
        mock_client.post.return_value = {
            "created": [{"id": "new-goal", "goal_name": goal_name}],
            "failed": [],
        }

        tool = self.tool_dict["create_goals"]
        item = AgentGoalCreateArgs(goal_name=goal_name)
        args = tool.args_model(items=[item])
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/goals")
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 0)

    @patch("src.agent.tools.factory._get_client")
    def test_update_handler(self, mock_get_client: MagicMock) -> None:
        """Test update_goal handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "goal-123", "goal_name": "Updated"}

        tool = self.tool_dict["update_goal"]
        args = tool.args_model(goal_id="goal-123", goal_name="Updated")
        result = tool.handler(args)

        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/goals/goal-123")
        # goal_id should not be in payload
        payload = call_args[1]["json"]
        self.assertNotIn("goal_id", payload)
        self.assertTrue(result["updated"])

    def test_update_no_properties_error(self) -> None:
        """Test update with no properties returns error."""
        tool = self.tool_dict["update_goal"]
        args = tool.args_model(goal_id="goal-123")
        result = tool.handler(args)

        self.assertFalse(result["updated"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
