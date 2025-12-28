"""Tests for the summariser module."""

import unittest
from unittest.mock import MagicMock, patch

from src.agent.exceptions import BedrockClientError
from src.alerts.formatters.summariser import (
    _generate_summary,
    _truncate_with_ellipsis,
    summarise_description,
)


class TestSummariseDescription(unittest.TestCase):
    """Tests for summarise_description function."""

    def test_short_description_unchanged(self) -> None:
        """Descriptions at or under max_length should not be summarised."""
        short = "This is a short description."
        result = summarise_description(short, max_length=150)
        self.assertEqual(result, short)

    def test_exact_length_unchanged(self) -> None:
        """Description exactly at max_length should not be summarised."""
        exact = "x" * 150
        result = summarise_description(exact, max_length=150)
        self.assertEqual(result, exact)

    @patch("src.alerts.formatters.summariser._generate_summary")
    def test_long_description_summarised(self, mock_generate: MagicMock) -> None:
        """Descriptions over max_length should be summarised."""
        mock_generate.return_value = "This is a summary."
        long_desc = "x" * 200

        result = summarise_description(long_desc, max_length=150)

        mock_generate.assert_called_once_with(long_desc, 150)
        self.assertEqual(result, "This is a summary.")

    @patch("src.alerts.formatters.summariser._generate_summary")
    def test_fallback_on_bedrock_error(self, mock_generate: MagicMock) -> None:
        """Should fall back to truncation if Bedrock fails."""
        mock_generate.side_effect = BedrockClientError("API error")
        long_desc = "This is a long description that exceeds the maximum length and needs to be truncated properly at a word boundary when AI summarisation fails."

        result = summarise_description(long_desc, max_length=100)

        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 100)


class TestGenerateSummary(unittest.TestCase):
    """Tests for _generate_summary function."""

    @patch("src.alerts.formatters.summariser.BedrockClient")
    def test_calls_bedrock_with_correct_params(self, mock_client_class: MagicMock) -> None:
        """Should call Bedrock with haiku model and correct prompt."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.converse.return_value = {}
        mock_client.parse_text_response.return_value = "Summary"

        result = _generate_summary("Long text to summarise", 150)

        mock_client.converse.assert_called_once()
        call_kwargs = mock_client.converse.call_args[1]
        self.assertEqual(call_kwargs["model_id"], "haiku")
        self.assertIn("150 characters", call_kwargs["messages"][0]["content"][0]["text"])
        self.assertEqual(result, "Summary")

    @patch("src.alerts.formatters.summariser.BedrockClient")
    def test_truncates_if_summary_too_long(self, mock_client_class: MagicMock) -> None:
        """Should truncate summary if AI returns more than max_length."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.converse.return_value = {}
        mock_client.parse_text_response.return_value = "x" * 200

        result = _generate_summary("Long text", 100)

        self.assertLessEqual(len(result), 100)
        self.assertTrue(result.endswith("..."))


class TestTruncateWithEllipsis(unittest.TestCase):
    """Tests for _truncate_with_ellipsis function."""

    def test_short_text_unchanged(self) -> None:
        """Text under max_length should not be truncated."""
        text = "Short text"
        result = _truncate_with_ellipsis(text, 50)
        self.assertEqual(result, text)

    def test_truncates_at_word_boundary(self) -> None:
        """Should truncate at a space if possible."""
        text = "This is a test sentence that is too long"
        result = _truncate_with_ellipsis(text, 25)

        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 25)
        # Should end cleanly without cutting a word
        self.assertNotIn("tha", result)

    def test_truncates_without_word_boundary_if_none_suitable(self) -> None:
        """Should truncate mid-word if no suitable space."""
        text = "Superlongwordwithoutanyspaces and more"
        result = _truncate_with_ellipsis(text, 20)

        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 20)

    def test_exact_length_unchanged(self) -> None:
        """Text exactly at max_length should not be truncated."""
        text = "x" * 50
        result = _truncate_with_ellipsis(text, 50)
        self.assertEqual(result, text)


if __name__ == "__main__":
    unittest.main()
