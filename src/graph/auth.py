"""Graph API Authentication."""

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from msal import PublicClientApplication, SerializableTokenCache
from requests import Response

from src.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 30


class GraphAuthenticationError(Exception):
    """Raised when Graph API authentication fails."""


class GraphAPI:
    """Client for Microsoft Graph API using device code authentication.

    Handles OAuth2 device code flow authentication and token caching for
    accessing Microsoft Graph API endpoints.
    """

    def __init__(
        self,
        target_upn: str,
        *,
        cache_file: Path | None = None,
    ) -> None:
        """Initialise the Graph API client.

        :param target_upn: The user principal name (email) of the target user.
        :param cache_file: Optional path to the token cache file.
            Defaults to 'msal_cache.bin' in the current directory.
        :raises KeyError: If required environment variables are not set.
        """
        logger.debug(f"Initialising GraphAPI client for upn={target_upn}")
        self._target_upn = target_upn

        self._tenant_id = os.environ["GRAPH_TENANT_ID"]
        self._client_id = os.environ["GRAPH_APPLICATION_ID"]
        self._authority = f"https://login.microsoftonline.com/{self._tenant_id}"
        self._scopes = ["Mail.Read"]

        self._cache_file = cache_file or PROJECT_ROOT / "msal_cache.bin"
        self._cache: SerializableTokenCache | None = None
        logger.debug(f"Token cache file configured at path={self._cache_file}")

        self._app = PublicClientApplication(
            client_id=self._client_id,
            authority=self._authority,
            token_cache=self.cache,
        )
        self._access_token: str | None = None
        self._access_expires: datetime | None = None
        logger.info(f"GraphAPI client initialised for upn={target_upn}")

    def _load_cache(self) -> SerializableTokenCache:
        """Load the token cache from disk.

        :returns: The deserialised token cache.
        """
        logger.debug(f"Loading token cache from path={self._cache_file}")
        cache = SerializableTokenCache()
        if self._cache_file.exists():
            cache.deserialize(self._cache_file.read_text())
            logger.debug(f"Token cache loaded from existing file path={self._cache_file}")
        else:
            logger.debug(f"Token cache file not found, using empty cache path={self._cache_file}")

        self._cache = cache
        return self._cache

    def _save_cache(self) -> None:
        """Save the token cache to disk.

        :raises ValueError: If cache has not been initialised.
        """
        if not self._cache:
            logger.error("Attempted to save cache before initialisation")
            raise ValueError("Cache not initialised")
        if self._cache.has_state_changed:
            self._cache_file.write_text(self._cache.serialize())
            logger.debug(f"Token cache saved to path={self._cache_file}")
        else:
            logger.debug("Token cache unchanged, skipping save")

    @property
    def cache(self) -> SerializableTokenCache:
        """Get the token cache, loading from disk if necessary.

        :returns: The token cache instance.
        """
        if not self._cache:
            return self._load_cache()
        return self._cache

    def _get_access_token(self) -> str:
        """Acquire an access token, using device code flow if necessary.

        Attempts silent token acquisition first. If that fails, initiates
        device code flow which requires user interaction.

        :returns: A valid access token.
        :raises GraphAuthenticationError: If device flow initiation fails.
        :raises GraphAuthenticationError: If token acquisition fails.
        """
        logger.debug(f"Acquiring access token for upn={self._target_upn}")
        accounts = self._app.get_accounts()
        logger.debug(f"Found cached_accounts_count={len(accounts)}")

        account = next(
            (a for a in accounts if a.get("username") == self._target_upn.lower()),
            None,
        )

        if account:
            logger.debug(f"Found matching cached account for upn={self._target_upn}")
            result = self._app.acquire_token_silent(self._scopes, account=account)
            if result:
                logger.debug("Silent token acquisition succeeded")
            else:
                logger.debug("Silent token acquisition returned no result")
        else:
            logger.debug(f"No cached account found for upn={self._target_upn}")
            result = None

        if not result:
            logger.info("Initiating device code flow for authentication")
            flow = self._app.initiate_device_flow(scopes=self._scopes)
            if "user_code" not in flow:
                logger.error(
                    f"Device flow initiation failed: {flow.get('error_description', flow)}"
                )
                raise GraphAuthenticationError(
                    f"Failed to initiate device flow: {flow.get('error_description', flow)}"
                )

            logger.info(f"Device code authentication required: {flow['message']}")
            result = self._app.acquire_token_by_device_flow(flow)
            logger.debug("Device code flow completed")

        self._save_cache()

        if "access_token" not in result:
            logger.error(f"Token acquisition failed: {result.get('error_description', result)}")
            raise GraphAuthenticationError(
                f"Failed to acquire token: {result.get('error_description', result)}"
            )

        self._access_token = result["access_token"]
        self._access_expires = datetime.now(UTC) + timedelta(seconds=result["expires_in"] - 10)
        logger.info(f"Access token acquired, expires_at={self._access_expires.isoformat()}")
        return self._access_token

    @property
    def access_token(self) -> str:
        """Get a valid access token, refreshing if expired.

        :returns: A valid access token.
        :raises RuntimeError: If access token expiration is not set.
        """
        if self._access_token is None:
            logger.debug("No access token cached, acquiring new token")
            return self._get_access_token()

        if self._access_expires is None:
            logger.error("Access token exists but expiration time is not set")
            raise RuntimeError("Access token expiration not set")

        if datetime.now(UTC) >= self._access_expires:
            logger.info(f"Access token expired at {self._access_expires.isoformat()}, refreshing")
            return self._get_access_token()

        logger.debug(f"Using cached access token, expires_at={self._access_expires.isoformat()}")
        return self._access_token

    @property
    def _url(self) -> str:
        """Base URL for the Graph API."""
        return f"https://graph.microsoft.com/v1.0/users/{self._target_upn}"

    @property
    def _headers(self) -> dict[str, str]:
        """Headers for the Graph API request."""
        return {"Authorization": f"Bearer {self.access_token}"}

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> Response:
        """Make a GET request to the Graph API.

        :param endpoint: The API endpoint path (e.g., 'messages', 'mailFolders').
        :param params: Optional query parameters to include in the request.
        :param timeout: Request timeout in seconds.
        :returns: The response from the Graph API.
        :raises requests.RequestException: If the request fails.
        """
        endpoint = endpoint.strip("/")
        url = f"{self._url}/{endpoint}"
        logger.debug(f"Making GET request to endpoint={endpoint}, timeout={timeout}s")

        response = requests.get(
            url,
            headers=self._headers,
            params=params,
            timeout=timeout,
        )

        logger.debug(
            f"Graph API response received: endpoint={endpoint}, status_code={response.status_code}"
        )
        if not response.ok:
            logger.warning(
                f"Graph API request failed: endpoint={endpoint}, "
                f"status_code={response.status_code}, reason={response.reason}"
            )

        return response


if __name__ == "__main__":
    load_dotenv()
    print(GraphAPI("oliver@oliverking.me.uk").access_token)
