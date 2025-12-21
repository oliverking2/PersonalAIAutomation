"""Parser for TLDR newsletter HTML content."""

import logging
import re
from urllib.parse import urlparse

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


def identify_newsletter_type(sender_name: str) -> NewsletterType:
    """Determine newsletter type from sender display name.

    :param sender_name: The sender display name (e.g., "TLDR AI", "TLDR Dev").
    :returns: The identified newsletter type.
    """
    sender_lower = sender_name.lower().strip()

    if "ai" in sender_lower:
        return NewsletterType.TLDR_AI
    if "dev" in sender_lower or "web dev" in sender_lower:
        return NewsletterType.TLDR_DEV

    return NewsletterType.TLDR


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
    current_section: str | None = None

    for block in text_blocks:
        if not isinstance(block, Tag):
            continue

        article = _extract_article_from_block(block, current_section)
        if article:
            articles.append(article)
            # Update current section if this article had one
            if article.section:
                current_section = article.section

    logger.info(f"Extracted {len(articles)} articles from newsletter")
    return articles


def _extract_article_from_block(
    block: Tag,
    current_section: str | None,
) -> ParsedArticle | None:
    """Extract article details from a single text-block element.

    :param block: The BeautifulSoup Tag representing the article block.
    :param current_section: The current section name (carried forward).
    :returns: A ParsedArticle if extraction succeeds, None otherwise.
    """
    # Find the first link - this is typically the article title/link
    link = block.find("a")
    if not link or not isinstance(link, Tag):
        return None

    href = link.get("href")
    if not href or not isinstance(href, str):
        return None

    # Skip non-article links (social media, unsubscribe, etc.)
    if not _is_article_url(href):
        return None

    title = link.get_text(strip=True)
    if not title:
        return None

    # Extract description - text after the link
    description = _extract_description(block, link)

    # Try to extract source publication from description
    source_publication = _extract_source_publication(description) if description else None

    # Try to extract section from block
    section = _extract_section(block) or current_section

    try:
        return ParsedArticle(
            title=title[:500],  # Truncate to max length
            url=HttpUrl(href),
            description=description,
            section=section[:2000] if section else None,
            source_publication=source_publication[:200] if source_publication else None,
        )
    except ValueError as e:
        logger.warning(f"Failed to create ParsedArticle: {e}")
        return None


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
            "twitter.com",
            "x.com",
            "facebook.com",
            "linkedin.com",
            "instagram.com",
            "tldrnewsletter.com",
            "list-manage.com",
            "mailchimp.com",
        }

        return not any(skip in domain for skip in skip_domains)
    except Exception:
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

    return full_text if full_text else None


def _extract_source_publication(text: str) -> str | None:
    """Extract source publication from article text.

    Looks for patterns like "(TechCrunch)" or "3 minute read".

    :param text: The article description text.
    :returns: The source publication name, or None if not found.
    """
    # Look for parenthetical source at end of text
    match = SOURCE_PATTERN.search(text)
    if match:
        source = match.group(1).strip()
        # Filter out read time patterns
        if not READ_TIME_PATTERN.match(source):
            return source

    return None


def _extract_section(block: Tag) -> str | None:
    """Extract the section name from an article block.

    TLDR newsletters typically have section headers like "BIG TECH & STARTUPS".

    :param block: The article block element.
    :returns: The section name, or None if not found.
    """
    # Look for section header in preceding siblings or parent elements
    # This is a simplified approach - may need refinement based on actual HTML structure

    # Check for bold/strong text that might be a section header
    strong = block.find("strong")
    if strong and isinstance(strong, Tag):
        text = strong.get_text(strip=True)
        # Section headers are typically ALL CAPS
        if text.isupper() and len(text) > MIN_SECTION_HEADER_LENGTH:
            return text.title()  # Convert to title case

    return None
