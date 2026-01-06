# Error Handling & Logging

Rules for exception handling, error messages, and logging.

## Exception Handling

### Never Use Bare Except

```python
# Bad: Catches everything, hides bugs
try:
    result = process_data()
except:
    pass

# Bad: Too broad, loses error context
try:
    result = process_data()
except Exception:
    return None

# Good: Catch specific exceptions
try:
    result = process_data()
except ValidationError as e:
    logger.warning(f"Invalid data: {e}")
    raise HTTPException(status_code=400, detail=str(e)) from e
except ConnectionError as e:
    logger.exception("Failed to connect to service")
    raise ServiceUnavailableError("Service temporarily unavailable") from e
```

### Custom Exceptions

Create domain-specific exceptions with useful context:

```python
class DomainError(Exception):
    """Base exception for domain errors."""
    pass


class ItemNotFoundError(DomainError):
    """Raised when an item cannot be found."""

    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(f"Item not found: {item_id}")


class ValidationError(DomainError):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"Validation failed for '{field}': {message}")
```

### Error Messages

Include actionable context in error messages:

```python
# Bad: Vague, unhelpful
raise ValueError("Invalid input")

# Good: Explains what failed, what was expected
raise ValueError(
    f"Invalid priority '{priority}'. "
    f"Expected one of: {', '.join(Priority)}"
)

# Good: Includes relevant identifiers
raise ItemNotFoundError(
    f"Task not found: id={task_id}. "
    "Verify the task exists and hasn't been deleted."
)
```

## Logging

### Setup

Use the standard library `logging` module with module-level loggers:

```python
import logging

logger = logging.getLogger(__name__)
```

### Log Levels

- **DEBUG**: Detailed flow information for debugging
- **INFO**: Significant actions and state changes
- **WARNING**: Unexpected but recoverable situations
- **ERROR**: Errors that need attention but don't crash the app
- **EXCEPTION**: Errors with full traceback (use `logger.exception()`)

```python
logger.debug(f"Processing item: id={item_id}, type={item_type}")
logger.info(f"Created task: id={task.id}, name={task.name}")
logger.warning(f"Retry {attempt}/3 after timeout: endpoint={endpoint}")
logger.error(f"Failed to send notification: chat_id={chat_id}")
logger.exception(f"Unexpected error processing message: update_id={update_id}")
```

### Structured Context

Include relevant identifiers, counts, and timings:

```python
# Good: Actionable context
logger.info(f"Processed batch: count={len(items)}, duration_ms={duration}")
logger.warning(f"Rate limited: endpoint={endpoint}, retry_after={retry_after}s")
logger.error(f"API call failed: endpoint={endpoint}, status={status}, error={error}")

# Bad: Missing context
logger.info("Processing complete")
logger.warning("Rate limited")
logger.error("API call failed")
```

### Never Log Secrets

```python
# Bad: Logs sensitive data
logger.debug(f"Authenticating with token={api_token}")
logger.info(f"User credentials: {credentials}")

# Good: Log metadata only
logger.debug(f"Authenticating: token_length={len(api_token)}")
logger.info(f"User authenticated: user_id={user_id}")
```

### No Print Statements

Never use `print()` in production code. Use logging instead.

```python
# Bad
print(f"Processing {item}")

# Good
logger.debug(f"Processing item: id={item.id}")
```

## HTTP Error Handling

For API endpoints, catch domain exceptions and convert to appropriate HTTP errors:

```python
from fastapi import HTTPException

@router.get("/{item_id}")
def get_item(item_id: str) -> ItemResponse:
    try:
        item = service.get_item(item_id)
        return ItemResponse.model_validate(item)
    except ItemNotFoundError:
        raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ExternalServiceError as e:
        logger.exception(f"External service failed for item: {item_id}")
        raise HTTPException(status_code=502, detail="External service unavailable") from e
```

## Timeout Handling

Always set timeouts for external calls:

```python
import requests

TIMEOUT_SECONDS = 30

try:
    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
except requests.exceptions.Timeout:
    logger.warning(f"Request timed out after {TIMEOUT_SECONDS}s: url={url}")
    raise ServiceTimeoutError(f"Request timed out: {url}")
except requests.exceptions.RequestException as e:
    logger.exception(f"Request failed: url={url}")
    raise ServiceError(f"Request failed: {e}") from e
```

## Exception Chaining

Always chain exceptions to preserve the original traceback:

```python
try:
    result = external_api.call()
except ExternalAPIError as e:
    # Use 'from e' to chain exceptions
    raise DomainError(f"External API failed: {e}") from e
```
