"""Substack API client with optional cookie-based authentication."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from time import sleep
from typing import Any

import requests

from src.paths import PROJECT_ROOT
from src.substack.constants import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    REQUEST_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


class SubstackClient:
    """HTTP client for Substack API requests.

    Handles rate limiting, headers, and optional cookie-based authentication.
    Can be used without cookies for public API endpoints.
    """

    def __init__(
        self,
        *,
        cookies_path: Path | None = None,
        rate_limit: bool = True,
    ) -> None:
        """Initialise the client.

        :param cookies_path: Optional path to cookies JSON file for authentication,
            defaults to PROJECT_ROOT/.substack/cookies.json.
        :param rate_limit: Whether to apply rate limiting between requests.
        """
        self.cookies_path = cookies_path or PROJECT_ROOT / ".substack" / "cookies.json"
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.authenticated = False

        self.session.headers.update(DEFAULT_HEADERS)

        if self.cookies_path and self.cookies_path.exists():
            self._load_cookies()
        elif self.cookies_path:
            logger.warning(f"Cookies file not found at {self.cookies_path}")

    def _load_cookies(self) -> None:
        """Load cookies from file and mark as authenticated.

        :raises ValueError: If cookies file is invalid.
        """
        if not self.cookies_path:
            return

        try:
            with self.cookies_path.open("r") as f:
                cookies = json.load(f)

            for cookie in cookies:
                self.session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/"),
                    secure=cookie.get("secure", False),
                )

            self.authenticated = True
            logger.debug(f"Loaded {len(cookies)} cookies from {self.cookies_path}")

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load cookies: {e}")
            raise ValueError(f"Invalid cookies file: {e}") from e

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting delay if enabled."""
        if self.rate_limit:
            sleep(REQUEST_DELAY_SECONDS)

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> requests.Response:
        """Make a GET request with rate limiting.

        :param url: URL to request.
        :param params: Optional query parameters.
        :param headers: Optional additional headers (merged with defaults).
        :param timeout: Request timeout in seconds.
        :returns: Response object.
        """
        request_headers = {**self.session.headers, **(headers or {})}
        response = self.session.get(
            url,
            params=params,
            headers=request_headers,
            timeout=timeout,
        )
        self._apply_rate_limit()
        return response

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Any:
        """Make a GET request and return JSON response.

        :param url: URL to request.
        :param params: Optional query parameters.
        :param headers: Optional additional headers (merged with defaults).
        :param timeout: Request timeout in seconds.
        :returns: Parsed JSON response.
        :raises requests.HTTPError: If the request fails.
        """
        response = self.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
