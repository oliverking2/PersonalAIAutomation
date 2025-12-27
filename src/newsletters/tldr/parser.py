"""Parser for TLDR newsletter HTML content."""

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl
from readability import Document

from src.newsletters.tldr.models import NewsletterType, ParsedArticle

logger = logging.getLogger(__name__)

# Regex pattern to extract source publication from article text
# Matches patterns like "3 minute read" or "(TechCrunch)"
SOURCE_PATTERN = re.compile(r"\(([^)]+)\)\s*$")
READ_TIME_PATTERN = re.compile(r"(\d+)\s*minute\s*read", re.IGNORECASE)

# Minimum length for section header text
MIN_SECTION_HEADER_LENGTH = 3

# Titles to exclude (case-insensitive exact matches)
EXCLUDED_TITLES: set[str] = {
    "apply here",
    "advertise with us",
}

# Substrings that indicate a title should be excluded (case-insensitive)
EXCLUDED_TITLE_SUBSTRINGS: set[str] = {
    "(sponsor)",
}


def identify_newsletter_type(sender_name: str) -> NewsletterType:
    """Determine newsletter type from sender display name.

    :param sender_name: The sender display name (e.g., "TLDR AI", "TLDR Dev").
    :returns: The identified newsletter type.
    """
    sender_lower = sender_name.lower().strip()

    if sender_lower == "tldr ai":
        return NewsletterType.TLDR_AI
    if sender_lower == "tldr dev":
        return NewsletterType.TLDR_DEV
    if sender_lower == "tldr data":
        return NewsletterType.TLDR_DATA
    if sender_lower == "tldr":
        return NewsletterType.TLDR

    raise ValueError(f"Unknown newsletter sender: {sender_name}")


def parse_newsletter_html(html: str) -> list[ParsedArticle]:
    """Parse newsletter HTML and extract articles.

    Uses readability to extract main content, then BeautifulSoup
    to find individual article blocks.

    :param html: The raw HTML content of the newsletter email.
    :returns: A list of parsed articles.
    """
    # Use readability to extract main content
    doc = Document(html)
    summary = doc.summary(html_partial=True)

    soup = BeautifulSoup(summary, "lxml")

    # Find all text blocks (article containers)
    text_blocks = soup.find_all(class_="text-block")

    articles: list[ParsedArticle] = []

    for block in text_blocks:
        if not isinstance(block, Tag):
            continue

        article = _extract_article_from_block(
            block,
        )
        if article:
            articles.append(article)

    logger.info(f"Extracted {len(articles)} articles from newsletter")
    return articles


def _unpack_href(href: str, *, timeout: int = 10) -> str:
    """Follow redirects to get the final destination URL.

    :param href: The URL to unpack (may contain tracking redirects).
    :param timeout: Request timeout in seconds.
    :returns: The final destination URL after following redirects.
    :raises requests.RequestException: If the request fails.
    """
    resp = requests.head(href, allow_redirects=True, timeout=timeout)
    # don't raise because sometimes the head comes back with a failure status but the url has been found
    return resp.url


def _extract_article_from_block(  # noqa: PLR0911
    block: Tag,
) -> ParsedArticle | None:
    """Extract article details from a single text-block element.

    :param block: The BeautifulSoup Tag representing the article block.
    :returns: A ParsedArticle if extraction succeeds, None otherwise.
    """
    # Find the first link - this is typically the article title/link
    link = block.find("a")
    if not link or not isinstance(link, Tag):
        logger.info(f"Skipping block without link: {block}")
        return None

    href = link.get("href")
    if not href or not isinstance(href, str):
        logger.info(f"Skipping link without href: {link}")
        return None

    # Skip non-article links if there are any (unsubscribe, etc.)
    if not _is_article_url(href):
        logger.info(f"Skipping non-article link: {href}")
        return None

    parsed_href = _unpack_href(href)
    logger.debug(f"Unpacked href: {parsed_href} -> {href}")

    title = link.get_text(strip=True)
    if not title:
        logger.info(f"Skipping link without title: {link}")
        return None

    # Skip excluded titles (sponsors, ads, job links)
    if _is_excluded_title(title):
        logger.debug(f"Skipping excluded title: {title}")
        return None

    # Extract description - text after the link
    description = _extract_description(block, link)

    try:
        return ParsedArticle(
            title=title[:500],  # Truncate to max length
            url=HttpUrl(href),
            url_parsed=HttpUrl(parsed_href),
            description=description,
        )
    except ValueError as e:
        logger.warning(f"Failed to create ParsedArticle: {e}")
        return None


def _is_excluded_title(title: str) -> bool:
    """Check if an article title should be excluded.

    Excludes sponsored content, job listings, and advertisement links.

    :param title: The article title to check.
    :returns: True if the title should be excluded.
    """
    title_lower = title.lower().strip()

    # Check exact matches
    if title_lower in EXCLUDED_TITLES:
        return True

    # Check substring matches
    return any(substring in title_lower for substring in EXCLUDED_TITLE_SUBSTRINGS)


def _is_article_url(url: str) -> bool:
    """Check if a URL is likely an article link.

    Filters out social media, newsletter management, and tracking links.

    :param url: The URL to check.
    :returns: True if the URL appears to be an article.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Skip common non-article domains
        skip_domains = {
            "list-manage.com",
            "mailchimp.com",
        }

        return not any(skip in domain for skip in skip_domains)
    except Exception:
        logger.warning(f"Failed to parse URL: {url}")
        return False


def _extract_description(block: Tag, title_link: Tag) -> str | None:
    """Extract the article description text.

    :param block: The article block element.
    :param title_link: The title link element to skip.
    :returns: The description text, or None if not found.
    """
    # Get all text content after the title link
    text_parts: list[str] = []

    for element in block.descendants:
        if element == title_link:
            continue
        if isinstance(element, str):
            text = element.strip()
            if text and text != title_link.get_text(strip=True):
                text_parts.append(text)

    full_text = " ".join(text_parts).strip()

    # Clean up the text
    full_text = re.sub(r"\s+", " ", full_text)
    if full_text is None:
        logger.warning(f"Failed to extract description from block: {block}")
        return None

    return full_text
