"""Tests for alert formatters."""

import unittest
from unittest.mock import MagicMock, patch

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

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that formatter returns (text, parse_mode) tuple."""
        alert = AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id="abc-123",
            title="TLDR AI",
            items=[],
        )

        result = format_newsletter_alert(alert)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIsInstance(text, str)

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

        text, parse_mode = format_newsletter_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        # Content should be present (MarkdownV2 escapes special chars)
        self.assertIn("TLDR AI", text)
        self.assertIn("GPT", text)
        self.assertIn("OpenAI announces GPT", text)
        self.assertIn("Claude Gets Smarter", text)

    @patch("src.alerts.formatters.formatters.summarise_description")
    def test_summarises_long_descriptions(self, mock_summarise: MagicMock) -> None:
        """Test that long descriptions are summarised."""
        long_desc = "x" * 200
        mock_summarise.return_value = "Summarised content"
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

        text, _parse_mode = format_newsletter_alert(alert)

        mock_summarise.assert_called_once_with(long_desc, max_length=150)
        self.assertIn("Summarised content", text)


class TestFormatTaskAlert(unittest.TestCase):
    """Tests for format_task_alert."""

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that formatter returns (text, parse_mode) tuple."""
        alert = AlertData(
            alert_type=AlertType.DAILY_TASK_WORK,
            source_id="2025-01-15-work",
            title="Work Tasks",
            items=[],
        )

        result = format_task_alert(alert)

        self.assertIsInstance(result, tuple)
        _text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")

    def test_formats_sections(self) -> None:
        """Test that tasks are organised into sections."""
        alert = AlertData(
            alert_type=AlertType.DAILY_TASK_WORK,
            source_id="2025-01-15-work",
            title="Work Tasks (Weekly Overview)",
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

        text, parse_mode = format_task_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("OVERDUE", text)
        self.assertIn("Overdue task", text)
        self.assertIn("3 days", text)
        self.assertIn("DUE TODAY", text)
        self.assertIn("Today task", text)
        self.assertIn("HIGH PRIORITY THIS WEEK", text)
        self.assertIn("Important task", text)

    def test_empty_sections_not_shown(self) -> None:
        """Test that empty sections are not rendered."""
        alert = AlertData(
            alert_type=AlertType.DAILY_TASK_WORK,
            source_id="2025-01-15-work",
            title="Work Tasks",
            items=[AlertItem(name="Today task", metadata={"section": "due_today"})],
        )

        text, _parse_mode = format_task_alert(alert)

        self.assertNotIn("OVERDUE", text)
        self.assertNotIn("HIGH PRIORITY", text)
        self.assertIn("DUE TODAY", text)

    def test_formats_due_date_as_human_readable(self) -> None:
        """Test that due dates are shown in human-readable format with day names."""
        alert = AlertData(
            alert_type=AlertType.DAILY_TASK_WORK,
            source_id="2025-01-15-work",
            title="Work Tasks",
            items=[
                AlertItem(
                    name="Important task",
                    metadata={"section": "high_priority_week", "due_date": "2025-01-18"},
                ),
            ],
        )

        text, _parse_mode = format_task_alert(alert)

        # Should show "Saturday 18th Jan 2025" format
        self.assertIn("Saturday", text)
        self.assertIn("18th", text)
        self.assertIn("Jan", text)
        self.assertNotIn("2025-01-18", text)


class TestFormatGoalAlert(unittest.TestCase):
    """Tests for format_goal_alert."""

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that formatter returns (text, parse_mode) tuple."""
        alert = AlertData(
            alert_type=AlertType.WEEKLY_GOAL,
            source_id="2025-W03",
            title="Weekly Goal Review",
            items=[],
        )

        result = format_goal_alert(alert)

        self.assertIsInstance(result, tuple)
        _text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")

    def test_formats_goals_with_progress(self) -> None:
        """Test that goals show progress bars."""
        alert = AlertData(
            alert_type=AlertType.WEEKLY_GOAL,
            source_id="2025-W03",
            title="Weekly Goal Review",
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

        text, parse_mode = format_goal_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Weekly Goal Review", text)
        self.assertIn("IN PROGRESS", text)
        self.assertIn("Learn Spanish", text)
        self.assertIn("75%", text)
        self.assertIn("NOT STARTED", text)
        self.assertIn("Read 24 books", text)


class TestFormatReadingAlert(unittest.TestCase):
    """Tests for format_reading_alert."""

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that formatter returns (text, parse_mode) tuple."""
        alert = AlertData(
            alert_type=AlertType.WEEKLY_READING,
            source_id="2025-W03",
            title="Weekly Reading List Reminder",
            items=[],
        )

        result = format_reading_alert(alert)

        self.assertIsInstance(result, tuple)
        _text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")

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

        text, parse_mode = format_reading_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Weekly Reading List Reminder", text)
        self.assertIn("HIGH PRIORITY", text)
        self.assertIn("Important Article", text)
        self.assertIn("GETTING STALE", text)
        self.assertIn("Old Book", text)


class TestFormatAlert(unittest.TestCase):
    """Tests for format_alert dispatcher."""

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that format_alert returns (text, parse_mode) tuple."""
        alert = AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id="1",
            title="Newsletter",
            items=[],
        )

        result = format_alert(alert)

        self.assertIsInstance(result, tuple)
        _text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")

    def test_dispatches_to_correct_formatter(self) -> None:
        """Test that format_alert calls the right formatter."""
        newsletter = AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id="1",
            title="Newsletter",
            items=[],
        )
        task = AlertData(
            alert_type=AlertType.DAILY_TASK_WORK,
            source_id="2",
            title="Tasks",
            items=[],
        )

        newsletter_text, _ = format_alert(newsletter)
        task_text, _ = format_alert(task)

        self.assertIn("Newsletter", newsletter_text)
        self.assertIn("Tasks", task_text)


if __name__ == "__main__":
    unittest.main()
