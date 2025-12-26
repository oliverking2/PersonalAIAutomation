"""Tests for agent content templates."""

import unittest
from datetime import date
from unittest.mock import patch

from src.agent.utils.templates import (
    build_goal_content,
    build_reading_item_content,
    build_task_content,
)


class TestBuildTaskContent(unittest.TestCase):
    """Tests for the build_task_content function."""

    @patch("src.agent.utils.templates.date")
    def test_basic_task_content(self, mock_date: unittest.mock.MagicMock) -> None:
        """Test building task content with description only."""
        mock_date.today.return_value = date(2025, 1, 15)

        result = build_task_content(description="Fix the authentication bug")

        self.assertIn("## Description", result)
        self.assertIn("Fix the authentication bug", result)
        self.assertIn("Created via AI Agent on 2025-01-15", result)
        self.assertNotIn("## Notes", result)

    @patch("src.agent.utils.templates.date")
    def test_task_content_with_notes(self, mock_date: unittest.mock.MagicMock) -> None:
        """Test building task content with description and notes."""
        mock_date.today.return_value = date(2025, 1, 15)

        result = build_task_content(
            description="Review the PR",
            notes="Check for security vulnerabilities",
        )

        self.assertIn("## Description", result)
        self.assertIn("Review the PR", result)
        self.assertIn("## Notes", result)
        self.assertIn("Check for security vulnerabilities", result)
        self.assertIn("Created via AI Agent on 2025-01-15", result)

    def test_task_content_has_separator(self) -> None:
        """Test that task content includes separator before timestamp."""
        result = build_task_content(description="Test task")

        self.assertIn("---", result)

    def test_task_content_structure(self) -> None:
        """Test that task content has correct structure."""
        result = build_task_content(
            description="Description text",
            notes="Notes text",
        )

        lines = result.split("\n")

        # Check structure order
        desc_index = lines.index("## Description")
        notes_index = lines.index("## Notes")
        separator_index = lines.index("---")

        self.assertLess(desc_index, notes_index)
        self.assertLess(notes_index, separator_index)


class TestBuildGoalContent(unittest.TestCase):
    """Tests for the build_goal_content function."""

    @patch("src.agent.utils.templates.date")
    def test_basic_goal_content(self, mock_date: unittest.mock.MagicMock) -> None:
        """Test building goal content with description only."""
        mock_date.today.return_value = date(2025, 2, 20)

        result = build_goal_content(description="Improve fitness by running daily")

        self.assertIn("## Description", result)
        self.assertIn("Improve fitness by running daily", result)
        self.assertIn("Created via AI Agent on 2025-02-20", result)
        self.assertNotIn("## Notes", result)

    @patch("src.agent.utils.templates.date")
    def test_goal_content_with_notes(self, mock_date: unittest.mock.MagicMock) -> None:
        """Test building goal content with description and notes."""
        mock_date.today.return_value = date(2025, 2, 20)

        result = build_goal_content(
            description="Learn a new programming language",
            notes="Start with Rust",
        )

        self.assertIn("## Description", result)
        self.assertIn("Learn a new programming language", result)
        self.assertIn("## Notes", result)
        self.assertIn("Start with Rust", result)

    def test_goal_content_has_separator(self) -> None:
        """Test that goal content includes separator before timestamp."""
        result = build_goal_content(description="Test goal")

        self.assertIn("---", result)


class TestBuildReadingItemContent(unittest.TestCase):
    """Tests for the build_reading_item_content function."""

    @patch("src.agent.utils.templates.date")
    def test_reading_content_without_notes(self, mock_date: unittest.mock.MagicMock) -> None:
        """Test building reading item content without notes."""
        mock_date.today.return_value = date(2025, 3, 10)

        result = build_reading_item_content()

        self.assertIn("## Notes", result)
        self.assertIn("(Add notes after reading)", result)
        self.assertIn("Added via AI Agent on 2025-03-10", result)

    @patch("src.agent.utils.templates.date")
    def test_reading_content_with_notes(self, mock_date: unittest.mock.MagicMock) -> None:
        """Test building reading item content with notes."""
        mock_date.today.return_value = date(2025, 3, 10)

        result = build_reading_item_content(notes="Recommended by colleague")

        self.assertIn("## Notes", result)
        self.assertIn("Recommended by colleague", result)
        self.assertNotIn("(Add notes after reading)", result)

    def test_reading_content_has_separator(self) -> None:
        """Test that reading content includes separator before timestamp."""
        result = build_reading_item_content()

        self.assertIn("---", result)

    def test_reading_content_uses_added_instead_of_created(self) -> None:
        """Test that reading content says 'Added' not 'Created'."""
        result = build_reading_item_content()

        self.assertIn("Added via AI Agent", result)
        self.assertNotIn("Created via AI Agent", result)


class TestTemplateConsistency(unittest.TestCase):
    """Tests for consistency across all template functions."""

    def test_all_templates_have_agent_attribution(self) -> None:
        """Test that all templates include AI Agent attribution."""
        task = build_task_content(description="test")
        goal = build_goal_content(description="test")
        reading = build_reading_item_content()

        self.assertIn("AI Agent", task)
        self.assertIn("AI Agent", goal)
        self.assertIn("AI Agent", reading)

    def test_all_templates_have_date(self) -> None:
        """Test that all templates include a date."""
        task = build_task_content(description="test")
        goal = build_goal_content(description="test")
        reading = build_reading_item_content()

        today = str(date.today())
        self.assertIn(today, task)
        self.assertIn(today, goal)
        self.assertIn(today, reading)

    def test_all_templates_return_strings(self) -> None:
        """Test that all templates return strings."""
        self.assertIsInstance(build_task_content(description="test"), str)
        self.assertIsInstance(build_goal_content(description="test"), str)
        self.assertIsInstance(build_reading_item_content(), str)


if __name__ == "__main__":
    unittest.main()
