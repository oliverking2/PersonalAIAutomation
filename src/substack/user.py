"""Substack user profile API wrapper."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any
from urllib.parse import urlparse

import requests

from src.substack.constants import DEFAULT_HEADERS, DEFAULT_TIMEOUT, SUBSTACK_BASE_URL

logger = logging.getLogger(__name__)


def resolve_handle_redirect(handle: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """Resolve a potentially renamed Substack handle by following redirects.

    :param handle: The original handle that may have been renamed.
    :param timeout: Request timeout in seconds.
    :returns: The new handle if renamed, None if no redirect or on error.
    """
    try:
        response = requests.get(
            f"{SUBSTACK_BASE_URL}/@{handle}",
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code == HTTPStatus.OK:
            parsed_url = urlparse(response.url)
            path_parts = parsed_url.path.strip("/").split("/")

            if path_parts and path_parts[0].startswith("@"):
                new_handle = path_parts[0][1:]

                if new_handle and new_handle != handle:
                    logger.info(f"Handle redirect detected: {handle} -> {new_handle}")
                    return new_handle

        return None

    except requests.RequestException as e:
        logger.debug(f"Error resolving handle redirect for {handle}: {e}")
        return None


class User:
    """Represents a Substack user profile.

    Provides access to user profile data including subscriptions.
    Handles renamed accounts by following redirects.
    """

    def __init__(self, username: str, *, follow_redirects: bool = True) -> None:
        """Initialise a User object.

        :param username: The user's Substack handle.
        :param follow_redirects: Whether to follow redirects for renamed accounts.
        """
        self.username = username
        self.original_username = username
        self.follow_redirects = follow_redirects
        self._user_data: dict[str, Any] | None = None
        self._redirect_attempted = False

    def __str__(self) -> str:
        """Return string representation."""
        return f"User: {self.username}"

    def __repr__(self) -> str:
        """Return repr string."""
        return f"User(username={self.username!r})"

    @property
    def _endpoint(self) -> str:
        """Get the API endpoint for this user."""
        return f"{SUBSTACK_BASE_URL}/api/v1/user/{self.username}/public_profile"

    def _update_handle(self, new_handle: str) -> None:
        """Update the user's handle after a redirect.

        :param new_handle: The new handle after redirect.
        """
        logger.info(f"Updating handle from {self.username} to {new_handle}")
        self.username = new_handle

    def _fetch_user_data(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch user data from the API with caching.

        Handles renamed accounts by following redirects when enabled.

        :param force_refresh: Whether to bypass the cache.
        :returns: Full user profile data.
        :raises requests.HTTPError: If the request fails.
        """
        if self._user_data is not None and not force_refresh:
            return self._user_data

        try:
            r = requests.get(self._endpoint, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            self._user_data = r.json()
            return self._user_data

        except requests.HTTPError as e:
            if (
                e.response is not None
                and e.response.status_code == HTTPStatus.NOT_FOUND
                and self.follow_redirects
                and not self._redirect_attempted
            ):
                self._redirect_attempted = True
                new_handle = resolve_handle_redirect(self.username)

                if new_handle:
                    self._update_handle(new_handle)

                    r = requests.get(
                        self._endpoint, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT
                    )
                    r.raise_for_status()
                    self._user_data = r.json()
                    return self._user_data

                logger.debug(f"No redirect found for {self.username}, user may be deleted")

            raise

    def get_raw_data(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Get the complete raw user data.

        :param force_refresh: Whether to bypass the cache.
        :returns: Full user profile data.
        """
        return self._fetch_user_data(force_refresh=force_refresh)

    @property
    def id(self) -> int:
        """Get the user's unique ID number.

        :returns: The user's ID.
        """
        return self._fetch_user_data()["id"]

    @property
    def name(self) -> str:
        """Get the user's display name.

        :returns: The user's name.
        """
        return self._fetch_user_data()["name"]

    @property
    def profile_set_up_at(self) -> str:
        """Get the date when the user's profile was set up.

        :returns: ISO 8601 formatted date string.
        """
        return self._fetch_user_data()["profile_set_up_at"]

    @property
    def was_redirected(self) -> bool:
        """Check if this user's handle was redirected from the original.

        :returns: True if the handle was redirected.
        """
        return self.username != self.original_username

    def get_subscriptions(self) -> list[dict[str, Any]]:
        """Get newsletters the user has subscribed to.

        :returns: List of subscription details with publication info.
        """
        data = self._fetch_user_data()
        subscriptions = []

        for sub in data.get("subscriptions", []):
            pub = sub["publication"]
            domain = pub.get("custom_domain") or f"{pub['subdomain']}.substack.com"
            subscriptions.append(
                {
                    "publication_id": pub["id"],
                    "publication_name": pub["name"],
                    "domain": domain,
                    "membership_state": sub["membership_state"],
                }
            )

        return subscriptions
