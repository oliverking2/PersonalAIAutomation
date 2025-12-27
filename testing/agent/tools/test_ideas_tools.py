"""Tests for ideas tool definitions."""

import unittest
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.ideas import IDEAS_TOOL_CONFIG, get_ideas_tools
from src.agent.tools.models import AgentIdeaCreateArgs
from src.api.notion.ideas.models import IdeaQueryRequest
from src.notion.enums import IdeaGroup


class TestIdeasToolDefinitions(unittest.TestCase):
    """Tests for ideas tool definitions."""

    def test_get_ideas_tools_returns_four_tools(self) -> None:
        """Test that get_ideas_tools returns all four tools."""
        tools = get_ideas_tools()

        self.assertEqual(len(tools), 4)
        tool_names = {t.name for t in tools}
        self.assertEqual(
            tool_names,
            {
                "query_ideas",
                "get_idea",
                "create_idea",
                "update_idea",
            },
        )

    def test_safe_tools(self) -> None:
        """Test that query, get, and create tools are marked as safe."""
        tools = get_ideas_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_ideas"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_idea"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["create_idea"].risk_level, RiskLevel.SAFE)

    def test_sensitive_tools(self) -> None:
        """Test that update tool is marked as sensitive."""
        tools = get_ideas_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["update_idea"].risk_level, RiskLevel.SENSITIVE)

    def test_tools_have_ideas_tag(self) -> None:
        """Test that all tools have the ideas tag."""
        tools = get_ideas_tools()

        for tool in tools:
            self.assertIn("ideas", tool.tags)

    def test_tools_generate_valid_json_schema(self) -> None:
        """Test that all tools generate valid JSON schemas."""
        tools = get_ideas_tools()

        for tool in tools:
            schema = tool.to_json_schema()
            self.assertIn("properties", schema)
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")


class TestIdeasToolConfig(unittest.TestCase):
    """Tests for IDEAS_TOOL_CONFIG."""

    def test_config_domain(self) -> None:
        """Test config has correct domain settings."""
        self.assertEqual(IDEAS_TOOL_CONFIG.domain, "idea")
        self.assertEqual(IDEAS_TOOL_CONFIG.domain_plural, "ideas")
        self.assertEqual(IDEAS_TOOL_CONFIG.endpoint_prefix, "/notion/ideas")
        self.assertEqual(IDEAS_TOOL_CONFIG.id_field, "idea_id")

    def test_config_enum_fields(self) -> None:
        """Test config has correct enum fields."""
        self.assertIn("idea_group", IDEAS_TOOL_CONFIG.enum_fields)


class TestIdeaQueryRequest(unittest.TestCase):
    """Tests for IdeaQueryRequest model (from API)."""

    def test_default_values(self) -> None:
        """Test default argument values."""
        args = IdeaQueryRequest()

        self.assertIsNone(args.idea_group)
        self.assertIsNone(args.name_filter)
        self.assertEqual(args.limit, 50)

    def test_all_filters(self) -> None:
        """Test setting all filter options."""
        args = IdeaQueryRequest(
            idea_group=IdeaGroup.WORK,
            name_filter="mobile app",
            limit=10,
        )

        self.assertEqual(args.idea_group, IdeaGroup.WORK)
        self.assertEqual(args.name_filter, "mobile app")
        self.assertEqual(args.limit, 10)


class TestAgentIdeaCreateArgs(unittest.TestCase):
    """Tests for AgentIdeaCreateArgs model."""

    def test_required_fields(self) -> None:
        """Test creating with required fields."""
        args = AgentIdeaCreateArgs(
            idea="Mobile app for habit tracking",
            notes="This app would help users build good habits using gamification",
        )

        self.assertEqual(args.idea, "Mobile app for habit tracking")
        self.assertEqual(
            args.notes, "This app would help users build good habits using gamification"
        )
        self.assertIsNone(args.idea_group)

    def test_full_args(self) -> None:
        """Test creating with all fields."""
        args = AgentIdeaCreateArgs(
            idea="CLI tool for task management",
            notes="A terminal-based task manager with vim-like keybindings",
            idea_group=IdeaGroup.PERSONAL,
        )

        self.assertEqual(args.idea, "CLI tool for task management")
        self.assertEqual(args.notes, "A terminal-based task manager with vim-like keybindings")
        self.assertEqual(args.idea_group, IdeaGroup.PERSONAL)


class TestIdeasToolHandlers(unittest.TestCase):
    """Tests for ideas tool handlers."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = get_ideas_tools()
        self.tool_dict = {t.name: t for t in self.tools}

    @patch("src.agent.tools.factory._get_client")
    def test_query_handler(self, mock_get_client: MagicMock) -> None:
        """Test query_ideas handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "idea-1"}]}

        tool = self.tool_dict["query_ideas"]
        args = IdeaQueryRequest(idea_group=IdeaGroup.WORK)
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/ideas/query")
        self.assertEqual(result["count"], 1)

    @patch("src.agent.tools.factory._get_client")
    def test_get_handler(self, mock_get_client: MagicMock) -> None:
        """Test get_idea handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "idea-123", "idea": "Test Idea"}

        tool = self.tool_dict["get_idea"]
        args = tool.args_model(idea_id="idea-123")
        result = tool.handler(args)

        mock_client.get.assert_called_once_with("/notion/ideas/idea-123")
        self.assertEqual(result["item"]["id"], "idea-123")

    @patch("src.agent.tools.factory._get_client")
    def test_create_handler(self, mock_get_client: MagicMock) -> None:
        """Test create_idea handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-idea", "idea": "New Idea"}

        tool = self.tool_dict["create_idea"]
        args = AgentIdeaCreateArgs(
            idea="New Idea",
            notes="Some details about this idea",
        )
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/ideas")
        # Content should be built from notes
        payload = call_args[1]["json"]
        self.assertIn("content", payload)
        self.assertTrue(result["created"])

    @patch("src.agent.tools.factory._get_client")
    def test_update_handler(self, mock_get_client: MagicMock) -> None:
        """Test update_idea handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "idea-123", "idea": "Updated"}

        tool = self.tool_dict["update_idea"]
        args = tool.args_model(idea_id="idea-123", idea="Updated")
        result = tool.handler(args)

        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/ideas/idea-123")
        # idea_id should not be in payload
        payload = call_args[1]["json"]
        self.assertNotIn("idea_id", payload)
        self.assertTrue(result["updated"])

    def test_update_no_properties_error(self) -> None:
        """Test update with no properties returns error."""
        tool = self.tool_dict["update_idea"]
        args = tool.args_model(idea_id="idea-123")
        result = tool.handler(args)

        self.assertFalse(result["updated"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
