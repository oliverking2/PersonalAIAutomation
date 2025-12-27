"""HTTP client for internal API calls."""

import logging
import os
from typing import Any

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# Default timeout for API requests in seconds
DEFAULT_TIMEOUT = 30

# HTTP status code threshold for errors
HTTP_ERROR_THRESHOLD = 400


class InternalAPIClientError(Exception):
    """Raised when an API request fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialise the error.

        :param message: Error message.
        :param status_code: HTTP status code if available.
        """
        super().__init__(message)
        self.status_code = status_code


class InternalAPIClient:
    """HTTP client for calling internal API endpoints.

    Provides authenticated access to API endpoints for use by alert providers,
    agent tool handlers, and other internal services.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the API client.

        :param base_url: Base URL for API. Defaults to AGENT_API_BASE_URL env var.
        :param api_token: API authentication token. Defaults to API_AUTH_TOKEN env var.
        :param timeout: Request timeout in seconds.
        :raises ValueError: If base_url or api_token is not configured.
        """
        self.base_url = base_url or os.environ.get("AGENT_API_BASE_URL", "http://localhost:8000")
        self.api_token = api_token or os.environ.get("API_AUTH_TOKEN")

        if not self.api_token:
            raise ValueError(
                "API authentication token not configured. Set API_AUTH_TOKEN environment variable."
            )

        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self.api_token}"})

        logger.debug(f"InternalAPIClient initialised: base_url={self.base_url}")

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the API.

        :param path: API endpoint path.
        :param params: Query parameters.
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a POST request to the API.

        :param path: API endpoint path.
        :param json: JSON request body.
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PATCH request to the API.

        :param path: API endpoint path.
        :param json: JSON request body.
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        return self._request("PATCH", path, json=json)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API.

        :param method: HTTP method.
        :param path: API endpoint path.
        :param params: Query parameters.
        :param json: JSON request body.
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        url = f"{self.base_url}{path}"

        try:
            logger.debug(f"API request: {method} {path} params={params} json={json}")
            response = self._session.request(
                method, url, params=params, json=json, timeout=self.timeout
            )

            if response.status_code >= HTTP_ERROR_THRESHOLD:
                error_detail = self._extract_error_detail(response)
                logger.warning(
                    f"API request failed: {method} {path} -> {response.status_code}: {error_detail}"
                )
                raise InternalAPIClientError(error_detail, status_code=response.status_code)

            return dict(response.json())

        except RequestException as e:
            logger.exception(f"API request error: {method} {path}")
            raise InternalAPIClientError(f"Request failed: {e}") from e

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str:
        """Extract error detail from response.

        :param response: HTTP response.
        :returns: Error message string.
        """
        try:
            data = response.json()
            if isinstance(data, dict):
                return str(data.get("detail", data))
            return str(data)
        except (ValueError, KeyError):
            return response.text or f"HTTP {response.status_code}"

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self) -> "InternalAPIClient":
        """Enter context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager."""
        self.close()
