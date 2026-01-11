"""Tests for agent content templates."""

import unittest

from src.agent.utils.templates import (
    build_goal_content,
    build_idea_content,
    build_reading_item_content,
    build_task_content,
)


class TestBuildTaskContent(unittest.TestCase):
    """Tests for the build_task_content function."""

    def test_description_only(self) -> None:
        """Test building task content with description only."""
        result = build_task_content(description="Fix the authentication bug")

        self.assertIn("## Description", result)
        self.assertIn("Fix the authentication bug", result)
        self.assertNotIn("## Notes", result)

    def test_notes_only(self) -> None:
        """Test building task content with notes only."""
        result = build_task_content(notes="Check for security vulnerabilities")

        self.assertNotIn("## Description", result)
        self.assertIn("## Notes", result)
        self.assertIn("Check for security vulnerabilities", result)

    def test_description_and_notes(self) -> None:
        """Test building task content with description and notes."""
        result = build_task_content(
            description="Review the PR",
            notes="Check for security vulnerabilities",
        )

        self.assertIn("## Description", result)
        self.assertIn("Review the PR", result)
        self.assertIn("## Notes", result)
        self.assertIn("Check for security vulnerabilities", result)

    def test_structure_order(self) -> None:
        """Test that description comes before notes."""
        result = build_task_content(
            description="Description text",
            notes="Notes text",
        )

        lines = result.split("\n")
        desc_index = lines.index("## Description")
        notes_index = lines.index("## Notes")

        self.assertLess(desc_index, notes_index)

    def test_empty_returns_empty(self) -> None:
        """Test that no inputs returns empty string."""
        result = build_task_content()
        self.assertEqual(result, "")


class TestBuildGoalContent(unittest.TestCase):
    """Tests for the build_goal_content function."""

    def test_description_only(self) -> None:
        """Test building goal content with description only."""
        result = build_goal_content(description="Improve fitness by running daily")

        self.assertIn("## Description", result)
        self.assertIn("Improve fitness by running daily", result)
        self.assertNotIn("## Notes", result)

    def test_description_and_notes(self) -> None:
        """Test building goal content with description and notes."""
        result = build_goal_content(
            description="Learn a new programming language",
            notes="Start with Rust",
        )

        self.assertIn("## Description", result)
        self.assertIn("Learn a new programming language", result)
        self.assertIn("## Notes", result)
        self.assertIn("Start with Rust", result)

    def test_empty_returns_empty(self) -> None:
        """Test that no inputs returns empty string."""
        result = build_goal_content()
        self.assertEqual(result, "")


class TestBuildReadingItemContent(unittest.TestCase):
    """Tests for the build_reading_item_content function."""

    def test_without_notes(self) -> None:
        """Test building reading item content without notes."""
        result = build_reading_item_content()

        self.assertIn("## Notes", result)
        self.assertIn("(Add notes after reading)", result)

    def test_with_notes(self) -> None:
        """Test building reading item content with notes."""
        result = build_reading_item_content(notes="Recommended by colleague")

        self.assertIn("## Notes", result)
        self.assertIn("Recommended by colleague", result)
        self.assertNotIn("(Add notes after reading)", result)


class TestBuildIdeaContent(unittest.TestCase):
    """Tests for the build_idea_content function."""

    def test_without_notes(self) -> None:
        """Test building idea content without notes."""
        result = build_idea_content()

        self.assertIn("## Details", result)
        self.assertIn("(Add details here)", result)

    def test_with_notes(self) -> None:
        """Test building idea content with notes."""
        result = build_idea_content(notes="This could be a mobile app")

        self.assertIn("## Details", result)
        self.assertIn("This could be a mobile app", result)
        self.assertNotIn("(Add details here)", result)


class TestTemplateConsistency(unittest.TestCase):
    """Tests for consistency across all template functions."""

    def test_all_templates_return_strings(self) -> None:
        """Test that all templates return strings."""
        self.assertIsInstance(build_task_content(description="test"), str)
        self.assertIsInstance(build_goal_content(description="test"), str)
        self.assertIsInstance(build_reading_item_content(), str)
        self.assertIsInstance(build_idea_content(), str)

    def test_all_templates_use_markdown_headings(self) -> None:
        """Test that all templates use markdown headings."""
        task = build_task_content(description="test")
        goal = build_goal_content(description="test")
        reading = build_reading_item_content()
        idea = build_idea_content()

        self.assertIn("##", task)
        self.assertIn("##", goal)
        self.assertIn("##", reading)
        self.assertIn("##", idea)


if __name__ == "__main__":
    unittest.main()
