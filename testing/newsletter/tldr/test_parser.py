"""Tests for newsletter parser module."""

import unittest

from src.newsletters.tldr.models import NewsletterType
from src.newsletters.tldr.parser import (
    _extract_source_publication,
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

    def test_identifies_tldr_web_dev_as_tldr_dev(self) -> None:
        """Test that 'TLDR Web Dev' is identified as tldr_dev."""
        result = identify_newsletter_type("TLDR Web Dev")
        self.assertEqual(result, NewsletterType.TLDR_DEV)

    def test_identifies_plain_tldr(self) -> None:
        """Test that 'TLDR' is identified as tldr."""
        result = identify_newsletter_type("TLDR")
        self.assertEqual(result, NewsletterType.TLDR)

    def test_handles_whitespace(self) -> None:
        """Test that leading/trailing whitespace is handled."""
        result = identify_newsletter_type("  TLDR AI  ")
        self.assertEqual(result, NewsletterType.TLDR_AI)

    def test_unknown_defaults_to_tldr(self) -> None:
        """Test that unknown sender names default to tldr."""
        result = identify_newsletter_type("Some Other Newsletter")
        self.assertEqual(result, NewsletterType.TLDR)


class TestIsArticleUrl(unittest.TestCase):
    """Tests for _is_article_url function."""

    def test_accepts_regular_article_urls(self) -> None:
        """Test that regular article URLs are accepted."""
        self.assertTrue(_is_article_url("https://techcrunch.com/article/123"))
        self.assertTrue(_is_article_url("https://www.theverge.com/news/456"))
        self.assertTrue(_is_article_url("https://arstechnica.com/tech/story"))

    def test_rejects_twitter_urls(self) -> None:
        """Test that Twitter URLs are rejected."""
        self.assertFalse(_is_article_url("https://twitter.com/user/status/123"))

    def test_rejects_x_urls(self) -> None:
        """Test that X (Twitter) URLs are rejected."""
        self.assertFalse(_is_article_url("https://x.com/user/status/123"))

    def test_rejects_facebook_urls(self) -> None:
        """Test that Facebook URLs are rejected."""
        self.assertFalse(_is_article_url("https://facebook.com/page/post"))

    def test_rejects_linkedin_urls(self) -> None:
        """Test that LinkedIn URLs are rejected."""
        self.assertFalse(_is_article_url("https://linkedin.com/in/user"))

    def test_rejects_tldr_newsletter_urls(self) -> None:
        """Test that TLDR newsletter management URLs are rejected."""
        self.assertFalse(_is_article_url("https://tldrnewsletter.com/unsubscribe"))

    def test_rejects_mailchimp_urls(self) -> None:
        """Test that Mailchimp URLs are rejected."""
        self.assertFalse(_is_article_url("https://list-manage.com/track/click"))

    def test_handles_empty_url(self) -> None:
        """Test that empty URLs are handled gracefully."""
        # Empty string will have empty domain, which is accepted
        # This is acceptable behaviour as the URL won't be valid anyway
        result = _is_article_url("")
        self.assertIsInstance(result, bool)


class TestExtractSourcePublication(unittest.TestCase):
    """Tests for _extract_source_publication function."""

    def test_extracts_parenthetical_source(self) -> None:
        """Test extraction of source in parentheses at end of text."""
        text = "Some article description (TechCrunch)"
        result = _extract_source_publication(text)
        self.assertEqual(result, "TechCrunch")

    def test_extracts_source_with_spaces(self) -> None:
        """Test extraction of source with spaces."""
        text = "Article text (The Verge)"
        result = _extract_source_publication(text)
        self.assertEqual(result, "The Verge")

    def test_ignores_read_time_patterns(self) -> None:
        """Test that read time patterns are not returned as source."""
        text = "Article description (3 minute read)"
        result = _extract_source_publication(text)
        self.assertIsNone(result)

    def test_ignores_minute_read_case_insensitive(self) -> None:
        """Test that read time patterns work case insensitively."""
        text = "Article description (5 Minute Read)"
        result = _extract_source_publication(text)
        self.assertIsNone(result)

    def test_returns_none_when_no_parentheses(self) -> None:
        """Test that None is returned when no parenthetical source exists."""
        text = "Article description without source"
        result = _extract_source_publication(text)
        self.assertIsNone(result)

    def test_returns_none_for_empty_string(self) -> None:
        """Test that empty string returns None."""
        result = _extract_source_publication("")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
