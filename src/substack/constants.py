"""Shared constants for Substack API client."""

# Standard browser User-Agent for requests
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.77 Safari/537.36"
)

# Default headers for Substack API requests
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
}

# Headers for discovery/search API endpoints
DISCOVERY_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "application/json",
    "Origin": "https://substack.com",
    "Referer": "https://substack.com/discover",
}

# API endpoints
SUBSTACK_BASE_URL = "https://substack.com"
SEARCH_URL = f"{SUBSTACK_BASE_URL}/api/v1/publication/search"
CATEGORIES_URL = f"{SUBSTACK_BASE_URL}/api/v1/categories"

# Rate limiting
REQUEST_DELAY_SECONDS = 2

# Pagination limits
DEFAULT_PAGE_SIZE = 15
MAX_CATEGORY_PAGES = 21

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30
