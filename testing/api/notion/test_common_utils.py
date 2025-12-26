"""Tests for common Notion API utilities."""

import unittest
from dataclasses import dataclass

from src.api.notion.common.utils import (
    DEFAULT_FUZZY_LIMIT,
    FUZZY_MATCH_THRESHOLD,
    MIN_TOKEN_LENGTH,
    filter_by_fuzzy_name,
)


@dataclass
class MockItem:
    """Mock item for testing fuzzy matching."""

    name: str


class TestFilterByFuzzyName(unittest.TestCase):
    """Tests for the filter_by_fuzzy_name function."""

    def setUp(self) -> None:
        """Set up test data."""
        self.items = [
            MockItem(name="Read emails"),
            MockItem(name="Write documentation"),
            MockItem(name="Review pull request"),
            MockItem(name="Email John about meeting"),
            MockItem(name="Calendar cleanup"),
            MockItem(name="Send email newsletter"),
            MockItem(name="Code review session"),
            MockItem(name="Team meeting notes"),
        ]
        self.name_getter = lambda x: x.name

    def test_no_filter_returns_all_items_with_none_quality(self) -> None:
        """Test that no filter returns all items up to limit with None quality."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter=None,
            name_getter=self.name_getter,
        )

        self.assertIsNone(quality)
        self.assertEqual(len(result), DEFAULT_FUZZY_LIMIT)

    def test_no_filter_respects_limit(self) -> None:
        """Test that no filter respects the limit parameter."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter=None,
            name_getter=self.name_getter,
            limit=3,
        )

        self.assertIsNone(quality)
        self.assertEqual(len(result), 3)

    def test_good_match_returns_good_quality(self) -> None:
        """Test that good fuzzy matches return 'good' quality."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter="email",
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "good")
        # Should match items containing "email"
        self.assertGreater(len(result), 0)
        # First result should be a strong match
        self.assertIn("email", result[0].name.lower())

    def test_fuzzy_match_finds_partial_matches(self) -> None:
        """Test that fuzzy matching finds partial text matches."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter="emails",  # plural
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "good")
        # Should still find "Read emails" and other email-related items
        names = [item.name.lower() for item in result]
        self.assertTrue(any("email" in name for name in names))

    def test_weak_match_returns_weak_quality(self) -> None:
        """Test that poor fuzzy matches return 'weak' quality."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter="xyznonexistent",
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "weak")
        # Should still return results (best guesses)
        self.assertGreater(len(result), 0)

    def test_short_tokens_are_filtered(self) -> None:
        """Test that tokens shorter than MIN_TOKEN_LENGTH are filtered."""
        # "the" and "to" should be filtered as they're < 3 chars
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter="the to email",
            name_getter=self.name_getter,
        )

        # Should match on "email" after filtering short tokens
        self.assertEqual(quality, "good")
        names = [item.name.lower() for item in result]
        self.assertTrue(any("email" in name for name in names))

    def test_limit_applied_to_fuzzy_results(self) -> None:
        """Test that limit is applied to fuzzy results."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter="email",
            name_getter=self.name_getter,
            limit=2,
        )

        self.assertEqual(quality, "good")
        self.assertLessEqual(len(result), 2)

    def test_case_insensitive_matching(self) -> None:
        """Test that fuzzy matching is case insensitive."""
        result, quality = filter_by_fuzzy_name(
            items=self.items,
            name_filter="EMAIL",
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "good")
        names = [item.name.lower() for item in result]
        self.assertTrue(any("email" in name for name in names))

    def test_empty_items_returns_empty(self) -> None:
        """Test that empty items list returns empty results."""
        result, quality = filter_by_fuzzy_name(
            items=[],
            name_filter="email",
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "weak")
        self.assertEqual(len(result), 0)

    def test_results_sorted_by_score_descending(self) -> None:
        """Test that results are sorted by match score descending."""
        items = [
            MockItem(name="Something else"),
            MockItem(name="Read emails daily"),
            MockItem(name="Email draft"),
        ]

        result, quality = filter_by_fuzzy_name(
            items=items,
            name_filter="email",
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "good")
        # Items with "email" should come before "Something else"
        email_indices = [i for i, item in enumerate(result) if "email" in item.name.lower()]
        other_indices = [i for i, item in enumerate(result) if "email" not in item.name.lower()]

        if email_indices and other_indices:
            self.assertLess(max(email_indices), min(other_indices))

    def test_threshold_determines_good_vs_weak(self) -> None:
        """Test that FUZZY_MATCH_THRESHOLD determines good vs weak quality."""
        # Create items that will have varying match scores
        items = [
            MockItem(name="Completely unrelated task"),
            MockItem(name="Another different thing"),
        ]

        # This should not match well
        _result, quality = filter_by_fuzzy_name(
            items=items,
            name_filter="email newsletter",
            name_getter=self.name_getter,
        )

        self.assertEqual(quality, "weak")

    def test_constants_have_expected_values(self) -> None:
        """Test that module constants have expected values."""
        self.assertEqual(MIN_TOKEN_LENGTH, 3)
        self.assertEqual(FUZZY_MATCH_THRESHOLD, 60)
        self.assertEqual(DEFAULT_FUZZY_LIMIT, 5)


if __name__ == "__main__":
    unittest.main()
