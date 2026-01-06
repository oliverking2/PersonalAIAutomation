# API Patterns

Rules for FastAPI endpoint structure and design.

## File Structure

API endpoints follow a modular structure organised by resource:

```
src/api/<domain>/
├── __init__.py           # Exports router
├── router.py             # Combines sub-routers
├── dependencies.py       # FastAPI dependencies (shared across resources)
├── common/
│   ├── __init__.py
│   ├── models.py         # Shared response models
│   └── utils.py          # Shared utility functions
└── <resource>/           # One directory per resource (e.g., tasks, pages)
    ├── __init__.py
    ├── endpoints.py      # FastAPI route handlers
    └── models.py         # Request/response Pydantic models
```

## Guidelines

- **One resource per directory**: Keep endpoints, models, and logic for each resource together.
- **Separate concerns**: `endpoints.py` handles HTTP, `models.py` defines schemas.
- **Shared code in `common/`**: Put reusable models and utilities in the `common/` subdirectory.
- **Dependencies at domain level**: Place FastAPI dependencies (e.g., `get_client`) in `dependencies.py`.
- **Avoid monolithic files**: Do not put all endpoints in a single `endpoints.py` file.

## Endpoint Structure

```python
from fastapi import APIRouter, Depends, HTTPException

from src.api.domain.dependencies import get_client
from src.api.domain.resource.models import CreateRequest, ItemResponse
from src.domain.client import DomainClient
from src.domain.exceptions import DomainError

router = APIRouter(prefix="/resource", tags=["resource"])


@router.post("", response_model=ItemResponse, summary="Create item")
def create_item(
    request: CreateRequest,
    client: DomainClient = Depends(get_client),
) -> ItemResponse:
    """Create a new item.

    :param request: Item creation data.
    :param client: Injected domain client.
    :returns: The created item.
    :raises HTTPException: If creation fails.
    """
    try:
        result = client.create(request.model_dump())
        return ItemResponse.model_validate(result)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
```

## Request/Response Models

- Separate request and response models.
- Use explicit Pydantic field constraints.
- Include metadata in responses where useful.

```python
from pydantic import BaseModel, Field

from src.domain.enums import Priority, Status


class CreateItemRequest(BaseModel):
    """Request to create a new item."""

    name: str = Field(..., min_length=1, max_length=200, description="Item name")
    priority: Priority = Field(default=Priority.MEDIUM, description="Priority level")


class ItemResponse(BaseModel):
    """Response containing item data."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Item name")
    status: Status = Field(..., description="Current status")
    priority: Priority = Field(..., description="Priority level")


class QueryResponse(BaseModel):
    """Response containing query results."""

    results: list[ItemResponse] = Field(..., description="Matching items")
    total: int = Field(..., description="Total count")
    excluded_done: bool = Field(default=False, description="Whether done items were excluded")
```

## Dependencies

Use FastAPI's dependency injection for shared resources:

```python
# src/api/domain/dependencies.py
import os
from functools import lru_cache

from src.domain.client import DomainClient


@lru_cache
def get_client() -> DomainClient:
    """Get configured domain client."""
    token = os.environ.get("DOMAIN_API_TOKEN")
    if not token:
        raise ValueError("DOMAIN_API_TOKEN not configured")
    return DomainClient(token=token)


def get_data_source_id() -> str:
    """Get configured data source ID."""
    source_id = os.environ.get("DATA_SOURCE_ID")
    if not source_id:
        raise ValueError("DATA_SOURCE_ID not configured")
    return source_id
```

## Error Handling

- Catch domain-specific exceptions and convert to appropriate HTTP errors.
- Include useful error details in the response.
- Log errors with context before raising HTTPException.

```python
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


@router.get("/{item_id}")
def get_item(item_id: str, client: DomainClient = Depends(get_client)) -> ItemResponse:
    try:
        result = client.get(item_id)
        return ItemResponse.model_validate(result)
    except ItemNotFoundError:
        raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
    except DomainError as e:
        logger.exception(f"Failed to get item: {item_id}")
        raise HTTPException(status_code=400, detail=str(e)) from e
```

## Bulk Operations

For endpoints that create/update multiple items:

- Accept a list of items in the request.
- Return both successful and failed items.
- Don't fail the entire request if some items fail.

```python
class BulkCreateResponse(BaseModel):
    """Response for bulk creation."""

    created: list[ItemResponse] = Field(default_factory=list)
    failed: list[BulkCreateFailure] = Field(default_factory=list)


class BulkCreateFailure(BaseModel):
    """Details of a failed creation."""

    index: int = Field(..., description="Index in the request list")
    name: str = Field(..., description="Item name that failed")
    error: str = Field(..., description="Error message")
```

## Authentication

Use HTTPBearer for token authentication:

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify the bearer token."""
    expected = os.environ.get("API_AUTH_TOKEN")
    if credentials.credentials != expected:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials
```
