"""Parser for Medium Daily Digest email HTML."""

import logging
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from src.newsletters.medium.models import ParsedMediumArticle

logger = logging.getLogger(__name__)

# Pattern to extract read time from text like "5 min read"
READ_TIME_PATTERN = re.compile(r"(\d+)\s*min\s*read", re.IGNORECASE)


def parse_medium_digest(html: str) -> list[ParsedMediumArticle]:
    """Parse a Medium Daily Digest email and extract articles.

    :param html: The raw HTML content of the email.
    :returns: A list of parsed articles.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find all h2 tags which contain article titles
    h2_tags = soup.find_all("h2")
    logger.debug(f"Found {len(h2_tags)} h2 tags in digest")

    articles: list[ParsedMediumArticle] = []
    seen_urls: set[str] = set()

    for h2 in h2_tags:
        article = _extract_article_from_h2(h2, seen_urls)
        if article is not None:
            articles.append(article)
            seen_urls.add(str(article.url))

    logger.info(f"Extracted {len(articles)} articles from Medium digest")
    return articles


def _extract_article_from_h2(h2: Tag, seen_urls: set[str]) -> ParsedMediumArticle | None:
    """Extract article data from an h2 tag.

    :param h2: The BeautifulSoup h2 tag.
    :param seen_urls: Set of URLs already seen (for deduplication).
    :returns: A ParsedMediumArticle or None if extraction fails.
    """
    # Get the title text
    title = h2.get_text(strip=True)
    if not title or _is_section_header(title):
        return None

    # Find the parent <a> tag containing the URL
    parent_link = h2.find_parent("a")
    if parent_link is None:
        return None

    href = parent_link.get("href")
    if not href or not isinstance(href, str):
        return None

    # Clean the URL (remove tracking parameters) and check for duplicates
    clean_url = _clean_medium_url(href)
    if not clean_url or clean_url in seen_urls:
        return None

    # Find the article block to extract description and read time
    article_block = _find_article_block(h2)

    description = _extract_description(article_block) if article_block else None
    read_time = _extract_read_time(article_block) if article_block else None

    # Append read time to title if available
    if read_time is not None:
        title = f"{title} ({read_time} min read)"

    return ParsedMediumArticle(
        title=title,
        url=HttpUrl(clean_url),
        description=description,
        read_time_minutes=read_time,
    )


def _is_section_header(title: str) -> bool:
    """Check if a title is a section header rather than an article title.

    :param title: The title text to check.
    :returns: True if this appears to be a section header.
    """
    section_headers = {
        "today's highlights",
        "from your following",
        "see more of what you like and less of what you don't.",
    }
    return title.lower().strip() in section_headers


def _find_article_block(h2: Tag) -> Tag | None:
    """Find the article block containing the h2 tag.

    Navigates up the DOM to find a parent div that contains the full article.

    :param h2: The h2 tag containing the article title.
    :returns: The article block div or None if not found.
    """
    # Navigate up to find a div that contains the article metadata
    current = h2.parent
    depth = 0
    max_depth = 10

    while current is not None and depth < max_depth:
        if isinstance(current, Tag) and current.name == "div":
            # Check if this div contains read time info (indicates article block)
            text = current.get_text()
            if "min read" in text.lower():
                return current
        current = current.parent
        depth += 1

    return None


def _extract_description(block: Tag) -> str | None:
    """Extract the article description from the article block.

    :param block: The article block tag.
    :returns: The description text or None if not found.
    """
    # Look for h3 tags which contain the article subtitle/description
    h3 = block.find("h3")
    if h3 is not None:
        text = h3.get_text(strip=True)
        if text:
            return text

    return None


def _extract_read_time(block: Tag) -> int | None:
    """Extract the read time from the article block.

    :param block: The article block tag.
    :returns: The read time in minutes or None if not found.
    """
    text = block.get_text()
    match = READ_TIME_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def _clean_medium_url(url: str) -> str | None:
    """Clean a Medium article URL by removing tracking parameters.

    :param url: The raw URL with tracking parameters.
    :returns: The cleaned URL or None if invalid.
    """
    try:
        parsed = urlparse(url)

        # Only process Medium URLs
        if "medium.com" not in parsed.netloc:
            return None

        # Remove query string (tracking parameters)
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",  # params
                "",  # query (removed)
                "",  # fragment
            )
        )
    except Exception:
        logger.debug(f"Failed to parse URL: {url}")
        return None
