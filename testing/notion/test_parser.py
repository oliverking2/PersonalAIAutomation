"""Tests for Notion parser module."""

import unittest
from datetime import date

from pydantic import ValidationError

from src.notion.models import TaskFilter
from src.notion.parser import (
    build_goal_properties,
    build_query_filter,
    build_reading_properties,
    build_task_properties,
    parse_page_to_goal,
    parse_page_to_reading_item,
    parse_page_to_task,
)


class TestParsePageToTask(unittest.TestCase):
    """Tests for parse_page_to_task function."""

    def test_parse_complete_page(self) -> None:
        """Test parsing a page with all properties populated."""
        page = {
            "id": "page-123",
            "url": "https://notion.so/My-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "My Task"}]},
                "Status": {"status": {"name": "In progress"}},
                "Due date": {"date": {"start": "2025-12-25"}},
                "Priority": {"select": {"name": "High"}},
                "Effort level": {"select": {"name": "Medium"}},
                "Task Group": {"select": {"name": "Work"}},
                "Assignee": {"people": [{"name": "John Doe"}]},
            },
        }

        task = parse_page_to_task(page)

        self.assertEqual(task.id, "page-123")
        self.assertEqual(task.task_name, "My Task")
        self.assertEqual(task.status, "In progress")
        self.assertEqual(task.due_date, date(2025, 12, 25))
        self.assertEqual(task.priority, "High")
        self.assertEqual(task.effort_level, "Medium")
        self.assertEqual(task.task_group, "Work")

    def test_parse_page_with_missing_optional_properties(self) -> None:
        """Test parsing a page with missing optional properties."""
        page = {
            "id": "page-456",
            "url": "https://notion.so/Minimal-Task",
            "properties": {
                "Task name": {"title": [{"plain_text": "Minimal Task"}]},
                "Status": {"status": None},
                "Due date": {"date": None},
                "Priority": {"select": None},
                "Effort level": {"select": None},
                "Task Group": {"select": None},
                "Description": {"rich_text": []},
                "Assignee": {"people": []},
            },
        }

        task = parse_page_to_task(page)

        self.assertEqual(task.id, "page-456")
        self.assertEqual(task.task_name, "Minimal Task")
        self.assertIsNone(task.status)
        self.assertIsNone(task.due_date)
        self.assertIsNone(task.priority)
        self.assertIsNone(task.effort_level)
        self.assertIsNone(task.task_group)

    def test_parse_page_with_multi_segment_title(self) -> None:
        """Test parsing a page with a title split across multiple segments."""
        page = {
            "id": "page-789",
            "url": "https://notion.so/Task",
            "properties": {
                "Task name": {
                    "title": [
                        {"plain_text": "Part 1 "},
                        {"plain_text": "Part 2"},
                    ],
                },
            },
        }

        task = parse_page_to_task(page)

        self.assertEqual(task.task_name, "Part 1 Part 2")

    def test_parse_page_with_empty_properties_raises_validation_error(self) -> None:
        """Test parsing a page with empty properties raises validation error."""
        page = {
            "id": "page-empty",
            "url": "",
            "properties": {},
        }

        with self.assertRaises(ValidationError):
            parse_page_to_task(page)


class TestBuildQueryFilter(unittest.TestCase):
    """Tests for build_query_filter function."""

    def test_build_filter_with_all_criteria(self) -> None:
        """Test building filter with all criteria specified."""
        filter_ = TaskFilter(
            status_not_equals="Complete",
            due_date_before=date(2025, 12, 31),
            has_title=True,
        )

        result = build_query_filter(filter_)

        self.assertIn("filter", result)
        self.assertIn("and", result["filter"])
        conditions = result["filter"]["and"]
        self.assertEqual(len(conditions), 3)

    def test_build_filter_with_status_only(self) -> None:
        """Test building filter with status criterion only."""
        filter_ = TaskFilter(
            status_not_equals="Done",
            has_title=False,
        )

        result = build_query_filter(filter_)

        self.assertIn("filter", result)
        self.assertEqual(result["filter"]["property"], "Status")
        self.assertEqual(result["filter"]["status"]["does_not_equal"], "Done")

    def test_build_filter_with_due_date_only(self) -> None:
        """Test building filter with due date criterion only."""
        filter_ = TaskFilter(
            due_date_before=date(2025, 6, 15),
            has_title=False,
        )

        result = build_query_filter(filter_)

        self.assertIn("filter", result)
        self.assertEqual(result["filter"]["property"], "Due date")
        self.assertEqual(result["filter"]["date"]["before"], "2025-06-15")

    def test_build_filter_with_no_criteria(self) -> None:
        """Test building filter with no criteria returns empty dict."""
        filter_ = TaskFilter(has_title=False)

        result = build_query_filter(filter_)

        self.assertEqual(result, {})

    def test_build_filter_with_title_only(self) -> None:
        """Test building filter with has_title criterion only."""
        filter_ = TaskFilter(has_title=True)

        result = build_query_filter(filter_)

        self.assertIn("filter", result)
        self.assertEqual(result["filter"]["property"], "Task name")
        self.assertTrue(result["filter"]["title"]["is_not_empty"])


class TestBuildTaskProperties(unittest.TestCase):
    """Tests for build_task_properties function."""

    def test_build_properties_with_all_fields(self) -> None:
        """Test building properties with all fields."""
        result = build_task_properties(
            task_name="New Task",
            status="Not started",
            due_date=date(2025, 12, 31),
            priority="High",
            effort_level="Medium",
            task_group="Work",
        )

        self.assertIn("Task name", result)
        self.assertIn("Status", result)
        self.assertIn("Due date", result)
        self.assertIn("Priority", result)
        self.assertIn("Effort level", result)
        self.assertIn("Task Group", result)

    def test_build_properties_with_name_only(self) -> None:
        """Test building properties with task name only."""
        result = build_task_properties(task_name="Simple Task")

        self.assertIn("Task name", result)
        self.assertEqual(len(result), 1)

    def test_build_properties_with_none_values_excluded(self) -> None:
        """Test that None values are excluded from properties."""
        result = build_task_properties(
            task_name="Task",
            status=None,
            priority="High",
        )

        self.assertIn("Task name", result)
        self.assertIn("Priority", result)
        self.assertNotIn("Status", result)

    def test_build_properties_with_no_fields_returns_empty(self) -> None:
        """Test building properties with no fields returns empty dict."""
        result = build_task_properties()

        self.assertEqual(result, {})

    def test_build_properties_unknown_field_raises_error(self) -> None:
        """Test that unknown field name raises ValueError."""
        with self.assertRaises(ValueError) as context:
            build_task_properties(unknown_field="value")

        self.assertIn("Unknown field", str(context.exception))

    def test_build_status_property(self) -> None:
        """Test building a status property."""
        result = build_task_properties(status="In progress")

        self.assertIn("Status", result)
        self.assertEqual(result["Status"]["status"]["name"], "In progress")

    def test_build_date_property(self) -> None:
        """Test building a date property."""
        result = build_task_properties(due_date=date(2025, 12, 25))

        self.assertIn("Due date", result)
        self.assertEqual(result["Due date"]["date"]["start"], "2025-12-25")

    def test_build_title_property(self) -> None:
        """Test building a title property."""
        result = build_task_properties(task_name="My New Task")

        self.assertIn("Task name", result)
        self.assertEqual(result["Task name"]["title"][0]["text"]["content"], "My New Task")

    def test_build_select_property(self) -> None:
        """Test building a select property."""
        result = build_task_properties(priority="High")

        self.assertIn("Priority", result)
        self.assertEqual(result["Priority"]["select"]["name"], "High")

    # def test_build_rich_text_property(self) -> None:
    #     """Test building a rich_text property."""
    #     result = build_task_properties(description="Task description")
    #
    #     self.assertIn("Description", result)
    #     self.assertEqual(
    #         result["Description"]["rich_text"][0]["text"]["content"],
    #         "Task description",
    #     )


class TestParsePageToGoal(unittest.TestCase):
    """Tests for parse_page_to_goal function."""

    def test_parse_complete_goal_page(self) -> None:
        """Test parsing a goal page with all properties populated."""
        page = {
            "id": "goal-123",
            "url": "https://notion.so/My-Goal",
            "properties": {
                "Goal name": {"title": [{"plain_text": "Learn Python"}]},
                "Status": {"status": {"name": "In progress"}},
                "Priority": {"select": {"name": "High"}},
                "Progress": {"number": 50},
                "Due date": {"date": {"start": "2025-12-31"}},
            },
        }

        goal = parse_page_to_goal(page)

        self.assertEqual(goal.id, "goal-123")
        self.assertEqual(goal.goal_name, "Learn Python")
        self.assertEqual(goal.status, "In progress")
        self.assertEqual(goal.priority, "High")
        self.assertEqual(goal.progress, 50)
        self.assertEqual(goal.due_date, date(2025, 12, 31))

    def test_parse_goal_page_with_missing_optional_properties(self) -> None:
        """Test parsing a goal page with missing optional properties."""
        page = {
            "id": "goal-456",
            "url": "https://notion.so/Minimal-Goal",
            "properties": {
                "Goal name": {"title": [{"plain_text": "Minimal Goal"}]},
                "Status": {"status": None},
                "Priority": {"select": None},
                "Progress": {"number": None},
                "Due date": {"date": None},
            },
        }

        goal = parse_page_to_goal(page)

        self.assertEqual(goal.id, "goal-456")
        self.assertEqual(goal.goal_name, "Minimal Goal")
        self.assertIsNone(goal.status)
        self.assertIsNone(goal.priority)
        self.assertIsNone(goal.progress)
        self.assertIsNone(goal.due_date)


class TestParsePageToReadingItem(unittest.TestCase):
    """Tests for parse_page_to_reading_item function."""

    def test_parse_complete_reading_item_page(self) -> None:
        """Test parsing a reading item page with all properties populated."""
        page = {
            "id": "reading-123",
            "url": "https://notion.so/My-Book",
            "properties": {
                "Title": {"title": [{"plain_text": "Clean Code"}]},
                "Type": {"select": {"name": "Book"}},
                "Status": {"status": {"name": "Reading Now"}},
                "Priority": {"select": {"name": "High"}},
                "Category": {"select": {"name": "Data Engineering"}},
                "URL": {"url": "https://example.com/book"},
            },
        }

        item = parse_page_to_reading_item(page)

        self.assertEqual(item.id, "reading-123")
        self.assertEqual(item.title, "Clean Code")
        self.assertEqual(item.item_type, "Book")
        self.assertEqual(item.status, "Reading Now")
        self.assertEqual(item.priority, "High")
        self.assertEqual(item.category, "Data Engineering")
        self.assertEqual(item.item_url, "https://example.com/book")

    def test_parse_reading_item_page_with_missing_optional_properties(self) -> None:
        """Test parsing a reading item page with missing optional properties."""
        page = {
            "id": "reading-456",
            "url": "https://notion.so/Minimal-Article",
            "properties": {
                "Title": {"title": [{"plain_text": "Minimal Article"}]},
                "Type": {"select": None},
                "Status": {"status": None},
                "Priority": {"select": None},
                "Category": {"select": None},
                "URL": {"url": None},
            },
        }

        item = parse_page_to_reading_item(page)

        self.assertEqual(item.id, "reading-456")
        self.assertEqual(item.title, "Minimal Article")
        self.assertEqual(item.item_type, "Other")  # Defaults to Other when None
        self.assertIsNone(item.status)
        self.assertIsNone(item.priority)
        self.assertIsNone(item.category)
        self.assertIsNone(item.item_url)


class TestBuildGoalProperties(unittest.TestCase):
    """Tests for build_goal_properties function."""

    def test_build_goal_properties_with_all_fields(self) -> None:
        """Test building goal properties with all fields."""
        result = build_goal_properties(
            goal_name="New Goal",
            status="Not started",
            priority="High",
            progress=25,
            due_date=date(2025, 12, 31),
        )

        self.assertIn("Goal name", result)
        self.assertIn("Status", result)
        self.assertIn("Priority", result)
        self.assertIn("Progress", result)
        self.assertIn("Due date", result)

    def test_build_goal_properties_with_name_only(self) -> None:
        """Test building goal properties with goal name only."""
        result = build_goal_properties(goal_name="Simple Goal")

        self.assertIn("Goal name", result)
        self.assertEqual(len(result), 1)

    def test_build_goal_number_property(self) -> None:
        """Test building a number property for progress."""
        result = build_goal_properties(progress=75)

        self.assertIn("Progress", result)
        self.assertEqual(result["Progress"]["number"], 75)

    def test_build_goal_properties_unknown_field_raises_error(self) -> None:
        """Test that unknown field name raises ValueError."""
        with self.assertRaises(ValueError) as context:
            build_goal_properties(unknown_field="value")

        self.assertIn("Unknown field", str(context.exception))


class TestBuildReadingProperties(unittest.TestCase):
    """Tests for build_reading_properties function."""

    def test_build_reading_properties_with_all_fields(self) -> None:
        """Test building reading properties with all fields."""
        result = build_reading_properties(
            title="New Article",
            item_type="Book",
            status="To Read",
            priority="High",
            category="Data Science",
            item_url="https://example.com/article",
        )

        self.assertIn("Title", result)
        self.assertIn("Type", result)
        self.assertIn("Status", result)
        self.assertIn("Priority", result)
        self.assertIn("Category", result)
        self.assertIn("URL", result)

    def test_build_reading_properties_with_title_only(self) -> None:
        """Test building reading properties with title only."""
        result = build_reading_properties(title="Simple Article")

        self.assertIn("Title", result)
        self.assertEqual(len(result), 1)

    def test_build_reading_url_property(self) -> None:
        """Test building a URL property."""
        result = build_reading_properties(item_url="https://example.com/book")

        self.assertIn("URL", result)
        self.assertEqual(result["URL"]["url"], "https://example.com/book")

    def test_build_reading_properties_unknown_field_raises_error(self) -> None:
        """Test that unknown field name raises ValueError."""
        with self.assertRaises(ValueError) as context:
            build_reading_properties(unknown_field="value")

        self.assertIn("Unknown field", str(context.exception))


if __name__ == "__main__":
    unittest.main()
