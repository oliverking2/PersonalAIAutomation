# Observability

Rules for logging, error tracking, metrics, and tracing.

## Structured Logging

### Log Format

Use consistent key-value pairs for machine-parseable logs:

```python
import logging

logger = logging.getLogger(__name__)

# Good: Structured with consistent keys
logger.info(f"Request completed: endpoint={endpoint}, status={status}, duration_ms={duration}")
logger.warning(f"Rate limited: service={service}, retry_after={retry_after}s")
logger.error(f"API call failed: endpoint={endpoint}, status_code={status}, error={error}")

# Bad: Unstructured, hard to parse
logger.info(f"The request to {endpoint} completed in {duration}ms")
logger.warning("We got rate limited, waiting before retry")
```

### Standard Context Fields

Include these fields consistently:

| Field         | When to use      | Example                    |
|---------------|------------------|----------------------------|
| `endpoint`    | HTTP requests    | `endpoint=/api/tasks`      |
| `status_code` | HTTP responses   | `status_code=404`          |
| `duration_ms` | Timed operations | `duration_ms=234`          |
| `count`       | Batch operations | `count=15`                 |
| `item_id`     | Single item ops  | `item_id=abc-123`          |
| `user_id`     | User context     | `user_id=user-456`         |
| `error`       | Error messages   | `error=Connection refused` |
| `attempt`     | Retries          | `attempt=2/3`              |

### Log Levels

```python
# DEBUG: Detailed flow for debugging (not shown in production by default)
logger.debug(f"Processing item: id={item_id}, type={item_type}, fields={fields}")

# INFO: Significant actions, state changes, milestones
logger.info(f"Created task: id={task.id}, name={task.name}")
logger.info(f"Batch processed: created={created}, failed={failed}, duration_ms={duration}")

# WARNING: Unexpected but recoverable, degraded performance
logger.warning(f"Retry {attempt}/3 after timeout: endpoint={endpoint}")
logger.warning(f"Cache miss rate high: rate={miss_rate:.1%}, threshold=10%")

# ERROR: Failures that need attention but don't crash the app
logger.error(f"Failed to send notification: chat_id={chat_id}, error={error}")

# EXCEPTION: Errors with full traceback (use logger.exception())
logger.exception(f"Unexpected error processing message: update_id={update_id}")
```

### Request Context

For web applications, include request context:

```python
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="")

# In middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# In handlers
logger.info(f"Processing request: request_id={request_id.get()}, path={path}")
```

## Sentry/GlitchTip Integration

### Setup

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


def init_sentry() -> None:
    """Initialise Sentry error tracking."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        logger.warning("SENTRY_DSN not configured, error tracking disabled")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,  # Sample 10% of transactions for performance
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        # Don't send PII
        send_default_pii=False,
    )
```

### Adding Context

```python
import sentry_sdk


def process_task(task_id: str, user_id: str) -> None:
    # Add context for error reports
    sentry_sdk.set_tag("task_id", task_id)
    sentry_sdk.set_user({"id": user_id})

    with sentry_sdk.push_scope() as scope:
        scope.set_extra("task_details", {"id": task_id, "status": "processing"})
        # If an error occurs here, it includes this context
        result = do_processing()
```

### Manual Error Capture

```python
try:
    result = risky_operation()
except ExpectedError as e:
    # Don't send expected errors to Sentry
    logger.warning(f"Expected error occurred: {e}")
    raise
except Exception as e:
    # Capture unexpected errors with context
    sentry_sdk.capture_exception(e)
    logger.exception("Unexpected error in risky_operation")
    raise
```

### Filtering Sensitive Data

```python
def before_send(event, hint):
    """Filter sensitive data before sending to Sentry."""
    # Remove sensitive headers
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        sensitive = ["authorization", "x-api-key", "cookie"]
        for key in sensitive:
            if key in headers:
                headers[key] = "[REDACTED]"

    return event


sentry_sdk.init(
    dsn=dsn,
    before_send=before_send,
)
```

## Timing Operations

### Context Manager Pattern

```python
import time
from contextlib import contextmanager
from collections.abc import Generator


@contextmanager
def timed_operation(operation: str) -> Generator[None, None, None]:
    """Log the duration of an operation."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{operation}: duration_ms={duration_ms:.1f}")


# Usage
with timed_operation("fetch_emails"):
    emails = email_client.fetch_all()
```

### Decorator Pattern

```python
import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def log_duration(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to log function execution time."""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(f"{func.__name__}: duration_ms={duration_ms:.1f}")
    return wrapper


@log_duration
def expensive_operation() -> list[Item]:
    return fetch_all_items()
```

## Health Checks

Expose health endpoints for monitoring:

```python
from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    external_api: str


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check service health."""
    db_status = "ok" if check_database() else "error"
    api_status = "ok" if check_external_api() else "error"

    return HealthResponse(
        status="ok" if db_status == "ok" and api_status == "ok" else "degraded",
        database=db_status,
        external_api=api_status,
    )


@router.get("/ready")
def readiness_check() -> dict[str, str]:
    """Check if service is ready to accept traffic."""
    return {"status": "ready"}
```

## Metrics (if using Prometheus)

```python
from prometheus_client import Counter, Histogram

# Define metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
)


# Record metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()

    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)

    return response
```

## What Not to Log

- Passwords, tokens, API keys
- Full request/response bodies with PII
- Credit card numbers, SSNs
- Email addresses (unless necessary for debugging)
- Session tokens or cookies

```python
# Bad
logger.debug(f"Auth request: token={api_token}, user={user_data}")

# Good
logger.debug(f"Auth request: token_prefix={api_token[:8]}..., user_id={user_id}")
```
