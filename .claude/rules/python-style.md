# Python Style Guide

Rules for Python code style, formatting, and type annotations.

## Python Version & Tooling

- Target Python 3.12 and above.
- Dependency management must use Poetry only.
- Do not introduce alternative env managers or install flows (pip, conda, uv, etc.).

## Type Annotations

- Use type annotations everywhere (public and internal).
- Avoid `Any` unless there is a clear, documented reason.
- Prefer precise types over broad ones:
  - Use `TypedDict`, `Protocol`, `Literal`, `NewType` where helpful
  - Use `dict[str, str]` not `dict[str, Any]` when the value type is known
- Use `X | None` syntax instead of `Optional[X]`.
- Add type stubs for third-party libraries where possible (add to poetry `dev` group).

## Mypy

- Aim for strict mode compliance.
- Do not silence errors with broad ignores.
- Avoid `# type: ignore` unless narrowly scoped and justified with a reason comment:
  ```python
  # type: ignore[arg-type]  # boto3 stubs don't match actual return type
  ```

## Formatting

- Ruff compatible formatting. Follow settings in `pyproject.toml`.
- Line length: 100 characters.
- Quote style: double quotes.
- Indent style: spaces.

## Naming

- British English spelling in comments, docstrings, user-facing text, and error messages.
- Constants: `UPPER_SNAKE_CASE`.
- Classes: `PascalCase`.
- Functions and variables: `snake_case`.
- Keep naming explicit and domain-aligned.
- Avoid vague verbs like `handle`, `do`, `process` without context.

## Imports

- Use absolute imports within `src/`.
- Sort imports with isort (handled by Ruff).
- Group imports: stdlib, third-party, local.

## Functions

- Prefer small, composable functions (aim: <50 lines, low branching).
- Avoid deeply nested logic. Use guard clauses and helper functions.
- Max cyclomatic complexity: 10.

## Enums

- Use `StrEnum` for any parameter or field with a defined set of valid string values.
- Never use string literals where an enum exists:
  ```python
  # Good
  status = TaskStatus.IN_PROGRESS

  # Bad
  status = "In Progress"
  ```
- Define enums in `enums.py` within the relevant module.
- StrEnum values automatically convert to strings for database storage and JSON serialisation.

## Docstrings

- Public functions/classes must include Sphinx-style docstrings:
  ```python
  def create_task(name: str, priority: Priority) -> NotionTask:
      """Create a new task in Notion.

      :param name: The task name.
      :param priority: Task priority level.
      :returns: The created task.
      :raises NotionClientError: If the API call fails.
      """
  ```

## Code Comments

- Add comments to explain **why**, not **what**.
- Only add comments for non-obvious logic: complex algorithms, business rules, workarounds, or edge cases.
- Avoid commenting self-explanatory code.
- Keep comments concise and up-to-date.

Good examples:
```python
# Group messages by chat to avoid multiple agent calls for rapid-fire messages
# Telegram API requires offset to be one greater than the last update_id
# Retry with backoff - Notion rate limits at 3 requests/second
```

Bad examples (avoid):
```python
# Increment counter  (obvious from code)
# Loop through items  (obvious from code)
```

## Pydantic

- Use Pydantic models for data validation and boundaries (API schemas, configs).
- Keep models typed precisely.
- Prefer explicit field constraints:
  ```python
  class CreateTaskRequest(BaseModel):
      task_name: str = Field(..., min_length=1, max_length=200)
      priority: Priority = Field(default=Priority.MEDIUM)
  ```
