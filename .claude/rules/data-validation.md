# Data Validation

Rules for validating data beyond basic Pydantic models.

## Validation Layers

Validate at each boundary:

```
External Input → API Validation → Business Validation → Database Constraints
```

| Layer    | Purpose                          | Tools                  |
|----------|----------------------------------|------------------------|
| API      | Format, types, basic constraints | Pydantic models        |
| Business | Domain rules, relationships      | Custom validators      |
| Database | Integrity, uniqueness            | SQLAlchemy constraints |

## Pydantic Validators

### Field Validators

```python
from pydantic import BaseModel, Field, field_validator
import re


class CreateTaskRequest(BaseModel):
    """Request to create a task."""

    task_name: str = Field(..., min_length=1, max_length=200)
    due_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    priority: str = Field(default="Medium")

    @field_validator("task_name")
    @classmethod
    def task_name_not_empty(cls, v: str) -> str:
        """Ensure task name has actual content."""
        if not v.strip():
            raise ValueError("Task name cannot be empty or whitespace only")
        return v.strip()

    @field_validator("priority")
    @classmethod
    def priority_valid(cls, v: str) -> str:
        """Validate priority is a known value."""
        allowed = {"Low", "Medium", "High", "Urgent"}
        if v not in allowed:
            raise ValueError(f"Priority must be one of: {', '.join(sorted(allowed))}")
        return v
```

### Model Validators

For validation that depends on multiple fields:

```python
from pydantic import BaseModel, model_validator


class DateRangeRequest(BaseModel):
    """Request with a date range."""

    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeRequest":
        """Ensure end_date is after start_date."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
```

### Before vs After Validation

```python
from pydantic import field_validator


class NormalisedInput(BaseModel):
    email: str
    tags: list[str]

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        """Normalise email before other validation."""
        if isinstance(v, str):
            return v.lower().strip()
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: str | list) -> list[str]:
        """Accept comma-separated string or list."""
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v
```

## Custom Validation Functions

### Reusable Validators

```python
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def validate_not_empty(value: str, field_name: str) -> str:
    """Validate string is not empty or whitespace."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    return value.strip()


def validate_in_range(
    value: T,
    min_val: T,
    max_val: T,
    field_name: str,
) -> T:
    """Validate value is within range."""
    if not min_val <= value <= max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}")
    return value


def validate_matches_pattern(
    value: str,
    pattern: str,
    field_name: str,
    message: str | None = None,
) -> str:
    """Validate string matches regex pattern."""
    if not re.match(pattern, value):
        raise ValueError(message or f"{field_name} has invalid format")
    return value
```

### Domain-Specific Validators

```python
from datetime import date


def validate_due_date(due_date: str | None, allow_past: bool = False) -> str | None:
    """Validate due date format and optionally check it's not in the past.

    :param due_date: Date string in YYYY-MM-DD format.
    :param allow_past: Whether to allow past dates.
    :returns: Validated date string.
    :raises ValueError: If date is invalid.
    """
    if due_date is None:
        return None

    try:
        parsed = date.fromisoformat(due_date)
    except ValueError as e:
        raise ValueError(f"Invalid date format '{due_date}', expected YYYY-MM-DD") from e

    if not allow_past and parsed < date.today():
        raise ValueError(f"Due date {due_date} is in the past")

    return due_date


def validate_url(url: str, allowed_schemes: set[str] | None = None) -> str:
    """Validate URL format and scheme.

    :param url: URL to validate.
    :param allowed_schemes: Allowed URL schemes (default: http, https).
    :returns: Validated URL.
    :raises ValueError: If URL is invalid.
    """
    from urllib.parse import urlparse

    allowed = allowed_schemes or {"http", "https"}

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid URL: {url}") from e

    if not parsed.scheme:
        raise ValueError(f"URL missing scheme: {url}")

    if parsed.scheme not in allowed:
        raise ValueError(f"URL scheme must be one of: {', '.join(allowed)}")

    if not parsed.netloc:
        raise ValueError(f"URL missing host: {url}")

    return url
```

## Sanitisation

### Text Sanitisation

```python
import re
import unicodedata


def sanitise_text(text: str, max_length: int | None = None) -> str:
    """Sanitise user text input.

    - Normalise unicode
    - Remove control characters
    - Collapse whitespace
    - Trim to max length

    :param text: Raw text input.
    :param max_length: Optional maximum length.
    :returns: Sanitised text.
    """
    # Normalise unicode
    text = unicodedata.normalize("NFKC", text)

    # Remove control characters (except newlines and tabs)
    text = "".join(c for c in text if c in "\n\t" or not unicodedata.category(c).startswith("C"))

    # Collapse multiple whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."

    return text


def sanitise_filename(filename: str) -> str:
    """Sanitise a filename for safe filesystem use.

    :param filename: Original filename.
    :returns: Safe filename.
    """
    # Remove path components
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove or replace dangerous characters
    filename = re.sub(r'[<>:"|?*]', "_", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Limit length
    if len(filename) > 200:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:195] + ("." + ext if ext else "")

    return filename or "unnamed"
```

### HTML Sanitisation

```python
import html
from typing import Literal


def escape_html(text: str) -> str:
    """Escape HTML entities for safe display."""
    return html.escape(text, quote=True)


def strip_html_tags(html_content: str) -> str:
    """Remove all HTML tags, keeping only text content."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)
```

## Enum Validation

### Using StrEnum

```python
from enum import StrEnum


class TaskStatus(StrEnum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class CreateTaskRequest(BaseModel):
    status: TaskStatus = Field(default=TaskStatus.NOT_STARTED)

    # Pydantic automatically validates against enum values
```

### Flexible Enum Matching

```python
def parse_status(value: str, enum_class: type[StrEnum]) -> StrEnum:
    """Parse a status string with flexible matching.

    Tries exact match, then case-insensitive match.

    :param value: Status string to parse.
    :param enum_class: Enum class to match against.
    :returns: Matching enum member.
    :raises ValueError: If no match found.
    """
    # Exact match
    for member in enum_class:
        if member.value == value:
            return member

    # Case-insensitive match
    value_lower = value.lower()
    for member in enum_class:
        if member.value.lower() == value_lower:
            return member

    valid = ", ".join(m.value for m in enum_class)
    raise ValueError(f"Invalid status '{value}'. Valid options: {valid}")
```

## Validation Error Responses

### Structured Error Format

```python
from pydantic import BaseModel


class ValidationErrorDetail(BaseModel):
    """Detail of a validation error."""

    field: str
    message: str
    value: str | None = None


class ValidationErrorResponse(BaseModel):
    """Response for validation errors."""

    detail: str = "Validation failed"
    errors: list[ValidationErrorDetail]


# In FastAPI exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        ValidationErrorDetail(
            field=".".join(str(loc) for loc in err["loc"]),
            message=err["msg"],
            value=str(err.get("input"))[:100] if err.get("input") else None,
        )
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ValidationErrorResponse(errors=errors).model_dump(),
    )
```

## Database-Level Validation

```python
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import validates


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 5", name="check_priority_range"),
        CheckConstraint("length(name) > 0", name="check_name_not_empty"),
        UniqueConstraint("name", "project_id", name="unique_task_per_project"),
    )

    @validates("status")
    def validate_status(self, key: str, value: str) -> str:
        """Validate status at ORM level."""
        allowed = {"not_started", "in_progress", "completed"}
        if value.lower() not in allowed:
            raise ValueError(f"Invalid status: {value}")
        return value
```
