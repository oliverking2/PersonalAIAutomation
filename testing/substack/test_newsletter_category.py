"""Tests for Substack newsletter category module."""

import unittest
from unittest.mock import MagicMock, patch

from src.substack.newsletter_category import Category, list_all_categories


class TestListAllCategories(unittest.TestCase):
    """Tests for list_all_categories function."""

    @patch("src.substack.newsletter_category._client")
    def test_returns_category_tuples(self, mock_client: MagicMock) -> None:
        """Test that list_all_categories returns tuples of (name, id)."""
        mock_client.get_json.return_value = [
            {"name": "Technology", "id": 1},
            {"name": "Culture", "id": 2},
        ]

        result = list_all_categories()

        self.assertEqual(result, [("Technology", 1), ("Culture", 2)])

    @patch("src.substack.newsletter_category._client")
    def test_returns_empty_list_when_no_categories(self, mock_client: MagicMock) -> None:
        """Test that empty list is returned when no categories exist."""
        mock_client.get_json.return_value = []

        result = list_all_categories()

        self.assertEqual(result, [])


class TestCategory(unittest.TestCase):
    """Tests for Category class."""

    def test_init_requires_name_or_id(self) -> None:
        """Test that ValueError is raised when neither name nor id provided."""
        with self.assertRaises(ValueError) as ctx:
            Category()

        self.assertIn("Either name or category_id must be provided", str(ctx.exception))

    @patch("src.substack.newsletter_category.list_all_categories")
    def test_init_with_name_resolves_id(self, mock_list_categories: MagicMock) -> None:
        """Test that initialising with name resolves the category ID."""
        mock_list_categories.return_value = [
            ("Technology", 1),
            ("Culture", 2),
        ]

        category = Category(name="Technology")

        self.assertEqual(category.name, "Technology")
        self.assertEqual(category.category_id, 1)

    @patch("src.substack.newsletter_category.list_all_categories")
    def test_init_with_id_resolves_name(self, mock_list_categories: MagicMock) -> None:
        """Test that initialising with ID resolves the category name."""
        mock_list_categories.return_value = [
            ("Technology", 1),
            ("Culture", 2),
        ]

        category = Category(category_id=2)

        self.assertEqual(category.name, "Culture")
        self.assertEqual(category.category_id, 2)

    def test_init_with_both_name_and_id(self) -> None:
        """Test that initialising with both name and ID works."""
        category = Category(name="Technology", category_id=1)

        self.assertEqual(category.name, "Technology")
        self.assertEqual(category.category_id, 1)

    @patch("src.substack.newsletter_category.list_all_categories")
    def test_init_with_invalid_name_raises_error(self, mock_list_categories: MagicMock) -> None:
        """Test that ValueError is raised for unknown category name."""
        mock_list_categories.return_value = [("Technology", 1)]

        with self.assertRaises(ValueError) as ctx:
            Category(name="Unknown")

        self.assertIn("Category name 'Unknown' not found", str(ctx.exception))

    @patch("src.substack.newsletter_category.list_all_categories")
    def test_init_with_invalid_id_raises_error(self, mock_list_categories: MagicMock) -> None:
        """Test that ValueError is raised for unknown category ID."""
        mock_list_categories.return_value = [("Technology", 1)]

        with self.assertRaises(ValueError) as ctx:
            Category(category_id=999)

        self.assertIn("Category ID 999 not found", str(ctx.exception))

    def test_str_representation(self) -> None:
        """Test string representation."""
        category = Category(name="Technology", category_id=1)

        self.assertEqual(str(category), "Technology (1)")

    def test_repr_representation(self) -> None:
        """Test repr representation."""
        category = Category(name="Technology", category_id=1)

        self.assertEqual(repr(category), "Category(name='Technology', category_id=1)")

    def test_get_newsletter_urls(self) -> None:
        """Test get_newsletter_urls returns list of URLs."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = {
            "publications": [
                {"base_url": "https://example1.substack.com"},
                {"base_url": "https://example2.substack.com"},
            ],
            "more": False,
        }

        category = Category(name="Technology", category_id=1, client=mock_client)
        urls = category.get_newsletter_urls()

        self.assertEqual(
            urls,
            ["https://example1.substack.com", "https://example2.substack.com"],
        )

    def test_get_newsletter_metadata(self) -> None:
        """Test get_newsletter_metadata returns full data."""
        mock_client = MagicMock()
        publications = [
            {"base_url": "https://example.substack.com", "name": "Example"},
        ]
        mock_client.get_json.return_value = {
            "publications": publications,
            "more": False,
        }

        category = Category(name="Technology", category_id=1, client=mock_client)
        metadata = category.get_newsletter_metadata()

        self.assertEqual(metadata, publications)

    def test_data_is_cached(self) -> None:
        """Test that newsletter data is cached after first fetch."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = {
            "publications": [{"base_url": "https://example.substack.com"}],
            "more": False,
        }

        category = Category(name="Technology", category_id=1, client=mock_client)
        category.get_newsletter_urls()
        category.get_newsletter_urls()

        mock_client.get_json.assert_called_once()

    def test_refresh_data_bypasses_cache(self) -> None:
        """Test that refresh_data forces a new fetch."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = {
            "publications": [{"base_url": "https://example.substack.com"}],
            "more": False,
        }

        category = Category(name="Technology", category_id=1, client=mock_client)
        category.get_newsletter_urls()
        category.refresh_data()

        self.assertEqual(mock_client.get_json.call_count, 2)

    def test_pagination_fetches_multiple_pages(self) -> None:
        """Test that multiple pages are fetched when more=True."""
        mock_client = MagicMock()
        mock_client.get_json.side_effect = [
            {
                "publications": [{"base_url": "https://page1.substack.com"}],
                "more": True,
            },
            {
                "publications": [{"base_url": "https://page2.substack.com"}],
                "more": False,
            },
        ]

        category = Category(name="Technology", category_id=1, client=mock_client)
        urls = category.get_newsletter_urls()

        self.assertEqual(
            urls,
            ["https://page1.substack.com", "https://page2.substack.com"],
        )
        self.assertEqual(mock_client.get_json.call_count, 2)


if __name__ == "__main__":
    unittest.main()
