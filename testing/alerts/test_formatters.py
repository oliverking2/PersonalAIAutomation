"""Tests for alert formatters."""

import unittest

from src.alerts.enums import AlertType
from src.alerts.formatters import (
    format_alert,
    format_goal_alert,
    format_newsletter_alert,
    format_reading_alert,
    format_task_alert,
)
from src.alerts.models import AlertData, AlertItem


class TestFormatNewsletterAlert(unittest.TestCase):
    """Tests for format_newsletter_alert."""

    def test_formats_newsletter_with_articles(self) -> None:
        """Test formatting a newsletter with articles."""
        alert = AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id="abc-123",
            title="TLDR AI - Latest news",
            items=[
                AlertItem(
                    name="New GPT-5 Announced",
                    url="https://example.com/gpt5",
                    metadata={"description": "OpenAI announces GPT-5"},
                ),
                AlertItem(
                    name="Claude Gets Smarter",
                    url="https://anthropic.com/claude",
                    metadata={"description": ""},
                ),
            ],
        )

        result = format_newsletter_alert(alert)

        self.assertIn("<b>TLDR AI - Latest news</b>", result)
        self.assertIn("<b>New GPT-5 Announced</b>", result)
        self.assertIn("OpenAI announces GPT-5", result)
        self.assertIn('<a href="https://example.com/gpt5">example.com</a>', result)
        self.assertIn("<b>Claude Gets Smarter</b>", result)

    def test_truncates_long_descriptions(self) -> None:
        """Test that long descriptions are truncated."""
        long_desc = "x" * 200
        alert = AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id="xyz",
            title="Test",
            items=[
                AlertItem(
                    name="Article", url="https://test.com", metadata={"description": long_desc}
                )
            ],
        )

        result = format_newsletter_alert(alert)

        self.assertIn("x" * 150, result)
        self.assertNotIn("x" * 151, result)


class TestFormatTaskAlert(unittest.TestCase):
    """Tests for format_task_alert."""

    def test_formats_sections(self) -> None:
        """Test that tasks are organised into sections."""
        alert = AlertData(
            alert_type=AlertType.DAILY_TASK,
            source_id="2025-01-15",
            title="Daily Task Summary",
            items=[
                AlertItem(
                    name="Overdue task", metadata={"section": "overdue", "days_overdue": "3"}
                ),
                AlertItem(name="Today task", metadata={"section": "due_today"}),
                AlertItem(
                    name="Important task",
                    metadata={"section": "high_priority_week", "due_date": "2025-01-18"},
                ),
            ],
        )

        result = format_task_alert(alert)

        self.assertIn("<b>OVERDUE (1)</b>", result)
        self.assertIn("Overdue task (3 days overdue)", result)
        self.assertIn("<b>DUE TODAY (1)</b>", result)
        self.assertIn("Today task", result)
        self.assertIn("<b>HIGH PRIORITY THIS WEEK (1)</b>", result)
        self.assertIn("Important task (Due: 2025-01-18)", result)

    def test_empty_sections_not_shown(self) -> None:
        """Test that empty sections are not rendered."""
        alert = AlertData(
            alert_type=AlertType.DAILY_TASK,
            source_id="2025-01-15",
            title="Daily Task Summary",
            items=[AlertItem(name="Today task", metadata={"section": "due_today"})],
        )

        result = format_task_alert(alert)

        self.assertNotIn("OVERDUE", result)
        self.assertNotIn("HIGH PRIORITY", result)
        self.assertIn("DUE TODAY", result)


class TestFormatGoalAlert(unittest.TestCase):
    """Tests for format_goal_alert."""

    def test_formats_goals_with_progress(self) -> None:
        """Test that goals show progress bars."""
        alert = AlertData(
            alert_type=AlertType.MONTHLY_GOAL,
            source_id="2025-01",
            title="Monthly Goal Review - January 2025",
            items=[
                AlertItem(
                    name="Learn Spanish",
                    metadata={"progress": "75", "status": "In progress", "due_date": "2025-03-01"},
                ),
                AlertItem(
                    name="Read 24 books",
                    metadata={"progress": "0", "status": "Not started", "due_date": ""},
                ),
            ],
        )

        result = format_goal_alert(alert)

        self.assertIn("<b>Monthly Goal Review - January 2025</b>", result)
        self.assertIn("IN PROGRESS (1)", result)
        self.assertIn("Learn Spanish", result)
        self.assertIn("75%", result)
        self.assertIn("NOT STARTED (1)", result)
        self.assertIn("Read 24 books", result)


class TestFormatReadingAlert(unittest.TestCase):
    """Tests for format_reading_alert."""

    def test_formats_reading_sections(self) -> None:
        """Test reading items organised by section."""
        alert = AlertData(
            alert_type=AlertType.WEEKLY_READING,
            source_id="2025-W03",
            title="Weekly Reading List Reminder",
            items=[
                AlertItem(
                    name="Important Article",
                    metadata={"section": "high_priority", "item_type": "Article"},
                ),
                AlertItem(name="Old Book", metadata={"section": "stale", "item_type": "Book"}),
            ],
        )

        result = format_reading_alert(alert)

        self.assertIn("<b>Weekly Reading List Reminder</b>", result)
        self.assertIn("HIGH PRIORITY (1)", result)
        self.assertIn("Important Article [Article]", result)
        self.assertIn("GETTING STALE (1)", result)
        self.assertIn("Old Book [Book]", result)


class TestFormatAlert(unittest.TestCase):
    """Tests for format_alert dispatcher."""

    def test_dispatches_to_correct_formatter(self) -> None:
        """Test that format_alert calls the right formatter."""
        newsletter = AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id="1",
            title="Newsletter",
            items=[],
        )
        task = AlertData(
            alert_type=AlertType.DAILY_TASK,
            source_id="2",
            title="Tasks",
            items=[],
        )

        newsletter_result = format_alert(newsletter)
        task_result = format_alert(task)

        self.assertIn("Newsletter", newsletter_result)
        self.assertIn("Tasks", task_result)


if __name__ == "__main__":
    unittest.main()
