"""HTTP client for internal API calls."""

import logging
import os
from typing import Any, cast

import httpx
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# Default timeout for API requests in seconds
DEFAULT_TIMEOUT = 60

# HTTP status code threshold for errors
HTTP_ERROR_THRESHOLD = 400

# HTTP 204 No Content status code
HTTP_NO_CONTENT = 204

# Default API configuration
DEFAULT_API_HOST = "localhost"
DEFAULT_API_PORT = "8000"


def _build_api_base_url() -> str:
    """Build API base URL from environment variables.

    Uses API_HOST and API_PORT environment variables to construct the URL.
    Defaults to localhost:8000 if not configured.

    :returns: Base URL for API (e.g., http://localhost:8000).
    """
    host = os.environ.get("API_HOST", DEFAULT_API_HOST)
    port = os.environ.get("API_PORT", DEFAULT_API_PORT)
    return f"http://{host}:{port}"


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

        :param base_url: Base URL for API. Defaults to http://{API_HOST}:{API_PORT}.
        :param api_token: API authentication token. Defaults to API_AUTH_TOKEN env var.
        :param timeout: Request timeout in seconds.
        :raises ValueError: If api_token is not configured.
        """
        self.base_url = base_url or _build_api_base_url()
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
        result = self._request("GET", path, params=params)
        return cast(dict[str, Any], result)

    def post(
        self, path: str, json: dict[str, Any] | list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make a POST request to the API.

        :param path: API endpoint path.
        :param json: JSON request body (dict or list of dicts).
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
        result = self._request("PATCH", path, json=json)
        return cast(dict[str, Any], result)

    def delete(self, path: str) -> None:
        """Make a DELETE request to the API.

        :param path: API endpoint path.
        :raises InternalAPIClientError: If the request fails.
        """
        self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make an HTTP request to the API.

        :param method: HTTP method.
        :param path: API endpoint path.
        :param params: Query parameters.
        :param json: JSON request body (dict or list of dicts).
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

            # Handle 204 No Content (e.g., DELETE responses)
            if response.status_code == HTTP_NO_CONTENT:
                return {}

            result = response.json()
            return list(result) if isinstance(result, list) else dict(result)

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


class AsyncInternalAPIClient:
    """Async HTTP client for calling internal API endpoints.

    Provides authenticated access to API endpoints using httpx for async operations.
    Used by async services like the Telegram handler for entity lookups.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the async API client.

        :param base_url: Base URL for API. Defaults to http://{API_HOST}:{API_PORT}.
        :param api_token: API authentication token. Defaults to API_AUTH_TOKEN env var.
        :param timeout: Request timeout in seconds.
        :raises ValueError: If api_token is not configured.
        """
        self.base_url = base_url or _build_api_base_url()
        self.api_token = api_token or os.environ.get("API_AUTH_TOKEN")

        if not self.api_token:
            raise ValueError(
                "API authentication token not configured. Set API_AUTH_TOKEN environment variable."
            )

        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

        logger.debug(f"AsyncInternalAPIClient initialised: base_url={self.base_url}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client.

        :returns: The httpx AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_token}"},
            )
        return self._client

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the API.

        :param path: API endpoint path.
        :param params: Query parameters.
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        result = await self._request("GET", path, params=params)
        return cast(dict[str, Any], result)

    async def post(
        self, path: str, json: dict[str, Any] | list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make a POST request to the API.

        :param path: API endpoint path.
        :param json: JSON request body (dict or list of dicts).
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        return await self._request("POST", path, json=json)

    async def patch(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PATCH request to the API.

        :param path: API endpoint path.
        :param json: JSON request body.
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        result = await self._request("PATCH", path, json=json)
        return cast(dict[str, Any], result)

    async def delete(self, path: str) -> None:
        """Make a DELETE request to the API.

        :param path: API endpoint path.
        :raises InternalAPIClientError: If the request fails.
        """
        await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make an async HTTP request to the API.

        :param method: HTTP method.
        :param path: API endpoint path.
        :param params: Query parameters.
        :param json: JSON request body (dict or list of dicts).
        :returns: JSON response data.
        :raises InternalAPIClientError: If the request fails.
        """
        url = f"{self.base_url}{path}"

        try:
            logger.debug(f"Async API request: {method} {path} params={params} json={json}")
            client = await self._get_client()
            response = await client.request(method, url, params=params, json=json)

            if response.status_code >= HTTP_ERROR_THRESHOLD:
                error_detail = self._extract_error_detail(response)
                logger.warning(
                    f"Async API request failed: {method} {path} -> "
                    f"{response.status_code}: {error_detail}"
                )
                raise InternalAPIClientError(error_detail, status_code=response.status_code)

            result = response.json()
            return list(result) if isinstance(result, list) else dict(result)

        except httpx.TimeoutException as e:
            logger.exception(f"Async API request timeout: {method} {path}")
            raise InternalAPIClientError(f"Request timed out: {e}") from e
        except httpx.HTTPError as e:
            logger.exception(f"Async API request error: {method} {path}")
            raise InternalAPIClientError(f"Request failed: {e}") from e

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
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

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncInternalAPIClient":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close()
