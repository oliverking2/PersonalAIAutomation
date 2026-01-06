# HTTP Client Patterns

Rules for making HTTP requests, handling retries, and managing connections.

## Choosing a Client

| Library    | Use Case                          |
|------------|-----------------------------------|
| `requests` | Simple sync requests, scripts     |
| `httpx`    | Async support, HTTP/2, modern API |
| `aiohttp`  | High-performance async            |

This project uses `requests` for sync and `httpx` for async.

## Basic Client Structure

### Sync Client (requests)

```python
import logging
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds


class APIClient:
    """Client for external API."""

    def __init__(self, base_url: str, api_token: str) -> None:
        self.base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def get(self, path: str, params: dict | None = None) -> dict:
        """Make a GET request."""
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> dict:
        """Make a POST request."""
        return self._request("POST", path, json=json)

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """Make an HTTP request with error handling."""
        url = f"{self.base_url}{path}"

        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out: {method} {path}")
            raise ServiceTimeoutError(f"Request timed out after {REQUEST_TIMEOUT}s") from e

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {method} {path} -> {e.response.status_code}")
            raise ServiceError(f"HTTP {e.response.status_code}: {e.response.text}") from e

        except RequestException as e:
            logger.exception(f"Request failed: {method} {path}")
            raise ServiceError(f"Request failed: {e}") from e

    def close(self) -> None:
        """Close the session."""
        self._session.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
```

### Async Client (httpx)

```python
import httpx
import logging

logger = logging.getLogger(__name__)


class AsyncAPIClient:
    """Async client for external API."""

    def __init__(self, base_url: str, api_token: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._headers,
            )
        return self._client

    async def get(self, path: str) -> dict:
        """Make an async GET request."""
        client = await self._get_client()
        response = await client.get(f"{self.base_url}{path}")
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict) -> dict:
        """Make an async POST request."""
        client = await self._get_client()
        response = await client.post(f"{self.base_url}{path}", json=json)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncAPIClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
```

## Retry Logic

### Exponential Backoff

```python
import time
import random
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (RequestException,),
) -> T:
    """Retry a function with exponential backoff.

    :param func: Function to retry.
    :param max_attempts: Maximum number of attempts.
    :param base_delay: Initial delay in seconds.
    :param max_delay: Maximum delay in seconds.
    :param retryable_exceptions: Exceptions that trigger retry.
    :returns: Function result.
    :raises: Last exception if all retries fail.
    """
    last_exception: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_attempts:
                logger.error(f"All {max_attempts} attempts failed")
                raise

            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            sleep_time = delay + jitter

            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed, "
                f"retrying in {sleep_time:.1f}s: {e}"
            )
            time.sleep(sleep_time)

    raise last_exception  # type: ignore[misc]
```

### Retryable Status Codes

```python
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable(response: requests.Response) -> bool:
    """Check if request should be retried based on status code."""
    return response.status_code in RETRYABLE_STATUS_CODES


def request_with_retry(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """Make a request with automatic retry for transient failures."""
    for attempt in range(1, 4):
        response = session.request(method, url, **kwargs)

        if not is_retryable(response):
            return response

        if attempt < 3:
            # Check for Retry-After header
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                delay = int(retry_after)
            else:
                delay = 2 ** attempt

            logger.warning(
                f"Retryable status {response.status_code}, "
                f"attempt {attempt}/3, waiting {delay}s"
            )
            time.sleep(delay)

    return response  # Return last response even if still failing
```

## Timeouts

Always set explicit timeouts:

```python
# Simple timeout (same for connect and read)
response = requests.get(url, timeout=30)

# Separate connect and read timeouts
response = requests.get(url, timeout=(5, 30))  # 5s connect, 30s read

# httpx with timeout configuration
client = httpx.Client(
    timeout=httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=30.0,
        pool=5.0,
    )
)
```

## Connection Pooling

### requests Session

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session() -> requests.Session:
    """Create a session with connection pooling and retry."""
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
    )

    # Configure connection pool
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
```

### httpx Connection Limits

```python
import httpx

# Configure connection limits
limits = httpx.Limits(
    max_keepalive_connections=10,
    max_connections=20,
    keepalive_expiry=30.0,
)

client = httpx.AsyncClient(limits=limits)
```

## Rate Limit Handling

```python
import time


class RateLimitedClient:
    """Client that respects rate limits."""

    def __init__(self, base_url: str, requests_per_second: float = 3.0) -> None:
        self.base_url = base_url
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._session = requests.Session()

    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def get(self, path: str) -> dict:
        """Make a rate-limited GET request."""
        self._wait_for_rate_limit()

        response = self._session.get(
            f"{self.base_url}{path}",
            timeout=30,
        )

        # Handle 429 responses
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            time.sleep(retry_after)
            return self.get(path)  # Retry

        response.raise_for_status()
        return response.json()
```

## Error Response Parsing

```python
def extract_error_detail(response: requests.Response) -> str:
    """Extract error message from API response."""
    try:
        data = response.json()
        # Try common error formats
        if isinstance(data, dict):
            return (
                data.get("error", {}).get("message")
                or data.get("detail")
                or data.get("message")
                or str(data)
            )
        return str(data)
    except (ValueError, KeyError):
        return response.text or f"HTTP {response.status_code}"
```

## Testing HTTP Clients

```python
from unittest.mock import MagicMock, patch


class TestAPIClient(unittest.TestCase):
    def setUp(self) -> None:
        self.client = APIClient(base_url="https://api.example.com", api_token="test")

    @patch("src.client.requests.Session.request")
    def test_get_returns_json(self, mock_request: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = self.client.get("/items/123")

        self.assertEqual(result, {"id": "123"})
        mock_request.assert_called_once()

    @patch("src.client.requests.Session.request")
    def test_timeout_raises_service_error(self, mock_request: MagicMock) -> None:
        mock_request.side_effect = requests.exceptions.Timeout()

        with self.assertRaises(ServiceTimeoutError):
            self.client.get("/items/123")
```
