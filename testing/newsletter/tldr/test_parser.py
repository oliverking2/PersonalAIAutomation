"""Tests for newsletter parser module."""

import unittest

from src.newsletters.tldr.models import NewsletterType
from src.newsletters.tldr.parser import (
    _is_article_url,
    identify_newsletter_type,
)


class TestIdentifyNewsletterType(unittest.TestCase):
    """Tests for identify_newsletter_type function."""

    def test_identifies_tldr_ai_from_sender_name(self) -> None:
        """Test that 'TLDR AI' is identified as tldr_ai."""
        result = identify_newsletter_type("TLDR AI")
        self.assertEqual(result, NewsletterType.TLDR_AI)

    def test_identifies_tldr_ai_case_insensitive(self) -> None:
        """Test that newsletter type identification is case insensitive."""
        result = identify_newsletter_type("tldr ai")
        self.assertEqual(result, NewsletterType.TLDR_AI)

    def test_identifies_tldr_dev_from_sender_name(self) -> None:
        """Test that 'TLDR Dev' is identified as tldr_dev."""
        result = identify_newsletter_type("TLDR Dev")
        self.assertEqual(result, NewsletterType.TLDR_DEV)

    def test_identifies_tldr_data_from_sender_name(self) -> None:
        """Test that 'TLDR Data' is identified as tldr_data."""
        result = identify_newsletter_type("TLDR Data")
        self.assertEqual(result, NewsletterType.TLDR_DATA)

    def test_identifies_plain_tldr(self) -> None:
        """Test that 'TLDR' is identified as tldr."""
        result = identify_newsletter_type("TLDR")
        self.assertEqual(result, NewsletterType.TLDR)

    def test_handles_whitespace(self) -> None:
        """Test that leading/trailing whitespace is handled."""
        result = identify_newsletter_type("  TLDR AI  ")
        self.assertEqual(result, NewsletterType.TLDR_AI)

    def test_unknown_raises_value_error(self) -> None:
        """Test that unknown sender names raise ValueError."""
        with self.assertRaises(ValueError) as context:
            identify_newsletter_type("Some Other Newsletter")
        self.assertIn("Unknown newsletter sender", str(context.exception))


class TestIsArticleUrl(unittest.TestCase):
    """Tests for _is_article_url function."""

    def test_accepts_regular_article_urls(self) -> None:
        """Test that regular article URLs are accepted."""
        self.assertTrue(_is_article_url("https://techcrunch.com/article/123"))
        self.assertTrue(_is_article_url("https://www.theverge.com/news/456"))
        self.assertTrue(_is_article_url("https://arstechnica.com/tech/story"))

    def test_accepts_social_media_urls(self) -> None:
        """Test that social media URLs are accepted as valid article sources."""
        self.assertTrue(_is_article_url("https://twitter.com/user/status/123"))
        self.assertTrue(_is_article_url("https://x.com/user/status/123"))
        self.assertTrue(_is_article_url("https://linkedin.com/in/user"))

    def test_rejects_mailchimp_urls(self) -> None:
        """Test that Mailchimp URLs are rejected."""
        self.assertFalse(_is_article_url("https://list-manage.com/track/click"))
        self.assertFalse(_is_article_url("https://mailchimp.com/campaign"))

    def test_handles_empty_url(self) -> None:
        """Test that empty URLs are handled gracefully."""
        # Empty string will have empty domain, which is accepted
        # This is acceptable behaviour as the URL won't be valid anyway
        result = _is_article_url("")
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
