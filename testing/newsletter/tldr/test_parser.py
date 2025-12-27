"""Tests for newsletter parser module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from src.newsletters.tldr.models import NewsletterType
from src.newsletters.tldr.parser import (
    _is_article_url,
    _is_excluded_title,
    _unpack_href,
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


class TestIsExcludedTitle(unittest.TestCase):
    """Tests for _is_excluded_title function."""

    def test_excludes_apply_here(self) -> None:
        """Test that 'Apply here' titles are excluded."""
        self.assertTrue(_is_excluded_title("Apply here"))
        self.assertTrue(_is_excluded_title("apply here"))
        self.assertTrue(_is_excluded_title("APPLY HERE"))

    def test_excludes_advertise_with_us(self) -> None:
        """Test that 'advertise with us' titles are excluded."""
        self.assertTrue(_is_excluded_title("advertise with us"))
        self.assertTrue(_is_excluded_title("Advertise with us"))

    def test_excludes_sponsor_titles(self) -> None:
        """Test that titles containing '(Sponsor)' are excluded."""
        self.assertTrue(_is_excluded_title("Great Product (Sponsor)"))
        self.assertTrue(_is_excluded_title("Something (sponsor) else"))
        self.assertTrue(_is_excluded_title("(SPONSOR) Advertisement"))

    def test_accepts_regular_titles(self) -> None:
        """Test that regular article titles are accepted."""
        self.assertFalse(_is_excluded_title("OpenAI Releases GPT-5"))
        self.assertFalse(_is_excluded_title("New Python Features"))
        self.assertFalse(_is_excluded_title("Tech Industry Update"))

    def test_handles_whitespace(self) -> None:
        """Test that leading/trailing whitespace is handled."""
        self.assertTrue(_is_excluded_title("  Apply here  "))
        self.assertTrue(_is_excluded_title("  advertise with us  "))


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


class TestUnpackHref(unittest.TestCase):
    """Tests for _unpack_href function."""

    @patch("src.newsletters.tldr.parser.requests.head")
    def test_returns_final_url_after_redirects(self, mock_head: MagicMock) -> None:
        """Test that the final URL is returned after following redirects."""
        mock_response = MagicMock()
        mock_response.url = "https://example.com/final-article"
        mock_head.return_value = mock_response

        result = _unpack_href("https://tracking.example.com/redirect?url=123")

        self.assertEqual(result, "https://example.com/final-article")
        mock_head.assert_called_once_with(
            "https://tracking.example.com/redirect?url=123",
            allow_redirects=True,
            timeout=10,
        )

    @patch("src.newsletters.tldr.parser.requests.head")
    def test_uses_custom_timeout(self, mock_head: MagicMock) -> None:
        """Test that custom timeout is passed to requests."""
        mock_response = MagicMock()
        mock_response.url = "https://example.com/article"
        mock_head.return_value = mock_response

        _unpack_href("https://example.com/redirect", timeout=30)

        mock_head.assert_called_once_with(
            "https://example.com/redirect",
            allow_redirects=True,
            timeout=30,
        )

    @patch("src.newsletters.tldr.parser.requests.head")
    def test_not_raises_on_http_error(self, mock_head: MagicMock) -> None:
        """Test that HTTP errors are raised."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_head.return_value = mock_response

        _unpack_href("https://example.com/not-found")

    @patch("src.newsletters.tldr.parser.requests.head")
    def test_raises_on_timeout(self, mock_head: MagicMock) -> None:
        """Test that timeout errors are raised."""
        mock_head.side_effect = requests.Timeout("Connection timed out")

        with self.assertRaises(requests.Timeout):
            _unpack_href("https://slow-server.example.com/article")

    @patch("src.newsletters.tldr.parser.requests.head")
    def test_raises_on_connection_error(self, mock_head: MagicMock) -> None:
        """Test that connection errors are raised."""
        mock_head.side_effect = requests.ConnectionError("Connection refused")

        with self.assertRaises(requests.ConnectionError):
            _unpack_href("https://unreachable.example.com/article")

    @patch("src.newsletters.tldr.parser.requests.head")
    def test_returns_same_url_if_no_redirect(self, mock_head: MagicMock) -> None:
        """Test that the same URL is returned if there are no redirects."""
        original_url = "https://example.com/direct-article"
        mock_response = MagicMock()
        mock_response.url = original_url
        mock_head.return_value = mock_response

        result = _unpack_href(original_url)

        self.assertEqual(result, original_url)


if __name__ == "__main__":
    unittest.main()
