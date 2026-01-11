"""Integration tests for content building in agent tools.

Run with: poetry run python -m unittest testing.agent.tools.test_validation_integration
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.agent.tools.factory import create_crud_tools
from src.agent.tools.goals import GOAL_TOOL_CONFIG
from src.agent.tools.models import (
    AgentGoalCreateArgs,
    AgentReadingItemCreateArgs,
    AgentTaskCreateArgs,
)
from src.agent.tools.reading_list import READING_LIST_TOOL_CONFIG
from src.agent.tools.tasks import TASK_TOOL_CONFIG
from src.notion.enums import GoalCategory, ReadingCategory, ReadingType


class TestTaskContentBuilding(unittest.TestCase):
    """Test task content building in the create handler."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = create_crud_tools(TASK_TOOL_CONFIG)
        self.create_tool = next(t for t in self.tools if t.name == "create_tasks")

    @patch("src.agent.tools.factory._get_client")
    def test_creates_task_successfully(self, mock_get_client: MagicMock) -> None:
        """Tasks should be created successfully."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "created": [{"id": "task-123", "task_name": "Test"}],
            "failed": [],
        }

        item = AgentTaskCreateArgs(
            task_name="Fix login bug",
            description="Check for common vulnerabilities in the auth module",
            notes="Focus on OWASP top 10",
            due_date=date(2025, 1, 15),
            task_group="Work",
        )
        args = self.create_tool.args_model(items=[item])
        result = self.create_tool.handler(args)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 0)
        mock_client.post.assert_called_once()

    @patch("src.agent.tools.factory._get_client")
    def test_content_is_built_from_description(self, mock_get_client: MagicMock) -> None:
        """Content should be built from description/notes, not passed directly."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"created": [{"id": "task-123"}], "failed": []}

        item = AgentTaskCreateArgs(
            task_name="Review Q4 budget proposal from finance",
            description="Review the quarterly budget numbers",
            notes="Check against last year's figures",
            due_date=date(2025, 1, 15),
            task_group="Work",
        )
        args = self.create_tool.args_model(items=[item])
        self.create_tool.handler(args)

        # Check the payload sent to API (items list)
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"][0]

        # Content should be built from template
        self.assertIn("content", payload)
        self.assertIn("## Description", payload["content"])
        self.assertIn("Review the quarterly budget numbers", payload["content"])
        self.assertIn("## Notes", payload["content"])
        self.assertIn("Check against last year's figures", payload["content"])

        # description/notes should NOT be in payload
        self.assertNotIn("description", payload)
        self.assertNotIn("notes", payload)

    @patch("src.agent.tools.factory._get_client")
    def test_task_without_description_creates_empty_content(
        self, mock_get_client: MagicMock
    ) -> None:
        """Tasks without description/notes should have empty content."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"created": [{"id": "task-123"}], "failed": []}

        item = AgentTaskCreateArgs(
            task_name="Review Q4 budget proposal from finance",
            due_date=date(2025, 1, 15),
            task_group="Work",
        )
        args = self.create_tool.args_model(items=[item])
        self.create_tool.handler(args)

        # Check the payload sent to API (items list)
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"][0]

        # Content should be present but empty when no description/notes
        self.assertIn("content", payload)
        self.assertEqual(payload["content"], "")
        self.assertNotIn("## Description", payload["content"])


class TestReadingListContentBuilding(unittest.TestCase):
    """Test reading list content building."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = create_crud_tools(READING_LIST_TOOL_CONFIG)
        self.create_tool = next(t for t in self.tools if t.name == "create_reading_list")

    @patch("src.agent.tools.factory._get_client")
    def test_creates_reading_item_successfully(self, mock_get_client: MagicMock) -> None:
        """Reading items should be created successfully."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"created": [{"id": "item-123"}], "failed": []}

        item = AgentReadingItemCreateArgs(
            title="Clean Code",
            item_type=ReadingType.BOOK,
            notes="Recommended by colleague",
            category=ReadingCategory.DATA_ANALYTICS,
        )
        args = self.create_tool.args_model(items=[item])
        result = self.create_tool.handler(args)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 0)

    @patch("src.agent.tools.factory._get_client")
    def test_reading_item_content_includes_notes(self, mock_get_client: MagicMock) -> None:
        """Reading item content should include notes."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"created": [{"id": "item-123"}], "failed": []}

        item = AgentReadingItemCreateArgs(
            title="Clean Code",
            item_type=ReadingType.BOOK,
            notes="Recommended by colleague",
            category=ReadingCategory.DATA_ANALYTICS,
        )
        args = self.create_tool.args_model(items=[item])
        self.create_tool.handler(args)

        # Check the payload sent to API (items list)
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"][0]

        self.assertIn("content", payload)
        self.assertIn("Recommended by colleague", payload["content"])
        self.assertNotIn("notes", payload)


class TestGoalContentBuilding(unittest.TestCase):
    """Test goal content building."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = create_crud_tools(GOAL_TOOL_CONFIG)
        self.create_tool = next(t for t in self.tools if t.name == "create_goals")

    @patch("src.agent.tools.factory._get_client")
    def test_creates_goal_successfully(self, mock_get_client: MagicMock) -> None:
        """Goals should be created successfully."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"created": [{"id": "goal-123"}], "failed": []}

        item = AgentGoalCreateArgs(
            goal_name="Run a half marathon by June 2025",
            description="Train for and complete a half marathon",
            category=GoalCategory.WORK,
            due_date=date(2025, 6, 15),
        )
        args = self.create_tool.args_model(items=[item])
        result = self.create_tool.handler(args)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 0)


if __name__ == "__main__":
    unittest.main()
