"""Tests for Medium digest parser."""

import unittest

from bs4 import BeautifulSoup

from src.newsletters.medium.parser import (
    _clean_medium_url,
    _extract_read_time,
    _is_section_header,
    parse_medium_digest,
)


class TestParseMediumDigest(unittest.TestCase):
    """Tests for parse_medium_digest function."""

    def test_parse_medium_digest_extracts_articles(self) -> None:
        """Should extract articles from Medium digest HTML."""
        html = """
        <html>
        <body>
            <div class="article-block">
                <div style="margin-top:16px">
                    <a href="https://medium.com/@author/article-slug?source=email-123">
                        <h2>Test Article Title</h2>
                    </a>
                    <div class="dv" style="margin-top:8px">
                        <h3>This is the article description.</h3>
                    </div>
                </div>
                <div style="margin-top:24px">
                    <span>5 min read</span>
                </div>
            </div>
        </body>
        </html>
        """
        articles = parse_medium_digest(html)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Test Article Title (5 min read)")
        self.assertEqual(str(articles[0].url), "https://medium.com/@author/article-slug")
        self.assertEqual(articles[0].description, "This is the article description.")
        self.assertEqual(articles[0].read_time_minutes, 5)

    def test_parse_medium_digest_handles_missing_read_time(self) -> None:
        """Should handle articles without read time."""
        html = """
        <html>
        <body>
            <div class="article-block">
                <div style="margin-top:16px">
                    <a href="https://medium.com/@author/article-slug?source=email-123">
                        <h2>Test Article Title</h2>
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        articles = parse_medium_digest(html)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Test Article Title")
        self.assertIsNone(articles[0].read_time_minutes)

    def test_parse_medium_digest_filters_section_headers(self) -> None:
        """Should not include section headers as articles."""
        html = """
        <html>
        <body>
            <div>
                <a href="#">
                    <h2>TODAY'S HIGHLIGHTS</h2>
                </a>
            </div>
            <div class="article-block">
                <div style="margin-top:16px">
                    <a href="https://medium.com/@author/real-article?source=email-123">
                        <h2>Real Article</h2>
                    </a>
                </div>
                <div><span>3 min read</span></div>
            </div>
        </body>
        </html>
        """
        articles = parse_medium_digest(html)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Real Article (3 min read)")

    def test_parse_medium_digest_handles_empty_html(self) -> None:
        """Should return empty list for empty HTML."""
        articles = parse_medium_digest("<html></html>")
        self.assertEqual(len(articles), 0)

    def test_parse_medium_digest_deduplicates_urls(self) -> None:
        """Should not include duplicate URLs."""
        html = """
        <html>
        <body>
            <div class="article-block">
                <a href="https://medium.com/@author/article?source=email-123">
                    <h2>First Article</h2>
                </a>
                <span>5 min read</span>
            </div>
            <div class="article-block">
                <a href="https://medium.com/@author/article?source=email-456">
                    <h2>Duplicate Article</h2>
                </a>
                <span>5 min read</span>
            </div>
        </body>
        </html>
        """
        articles = parse_medium_digest(html)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "First Article (5 min read)")


class TestCleanMediumUrl(unittest.TestCase):
    """Tests for _clean_medium_url function."""

    def test_clean_medium_url_removes_tracking_params(self) -> None:
        """Should remove query parameters from URL."""
        url = "https://medium.com/@author/article-slug?source=email-123-digest"
        clean = _clean_medium_url(url)
        self.assertEqual(clean, "https://medium.com/@author/article-slug")

    def test_clean_medium_url_preserves_path(self) -> None:
        """Should preserve the full path."""
        url = "https://medium.com/publication/article-title-abc123def456?source=email"
        clean = _clean_medium_url(url)
        self.assertEqual(clean, "https://medium.com/publication/article-title-abc123def456")

    def test_clean_medium_url_rejects_non_medium_urls(self) -> None:
        """Should return None for non-Medium URLs."""
        url = "https://example.com/article"
        clean = _clean_medium_url(url)
        self.assertIsNone(clean)

    def test_clean_medium_url_handles_already_clean_url(self) -> None:
        """Should handle URLs without query params."""
        url = "https://medium.com/@author/article-slug"
        clean = _clean_medium_url(url)
        self.assertEqual(clean, "https://medium.com/@author/article-slug")


class TestIsSectionHeader(unittest.TestCase):
    """Tests for _is_section_header function."""

    def test_is_section_header_detects_todays_highlights(self) -> None:
        """Should detect 'TODAY'S HIGHLIGHTS' as section header."""
        self.assertTrue(_is_section_header("TODAY'S HIGHLIGHTS"))
        self.assertTrue(_is_section_header("today's highlights"))
        self.assertTrue(_is_section_header("  Today's Highlights  "))

    def test_is_section_header_detects_from_your_following(self) -> None:
        """Should detect 'FROM YOUR FOLLOWING' as section header."""
        self.assertTrue(_is_section_header("FROM YOUR FOLLOWING"))
        self.assertTrue(_is_section_header("from your following"))

    def test_is_section_header_rejects_article_titles(self) -> None:
        """Should not classify article titles as section headers."""
        self.assertFalse(_is_section_header("How to Build a Real App"))
        self.assertFalse(_is_section_header("10 Python Tips"))


class TestExtractReadTime(unittest.TestCase):
    """Tests for _extract_read_time function."""

    def test_extract_read_time_single_digit(self) -> None:
        """Should extract single digit read time."""
        html = "<div><span>5 min read</span></div>"
        soup = BeautifulSoup(html, "lxml")
        result = _extract_read_time(soup.find("div"))
        self.assertEqual(result, 5)

    def test_extract_read_time_double_digit(self) -> None:
        """Should extract double digit read time."""
        html = "<div><span>12 min read</span></div>"
        soup = BeautifulSoup(html, "lxml")
        result = _extract_read_time(soup.find("div"))
        self.assertEqual(result, 12)

    def test_extract_read_time_returns_none_when_missing(self) -> None:
        """Should return None when no read time found."""
        html = "<div><span>Some other text</span></div>"
        soup = BeautifulSoup(html, "lxml")
        result = _extract_read_time(soup.find("div"))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
