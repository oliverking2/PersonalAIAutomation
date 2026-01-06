# Testing Standards

Rules for writing and organising tests.

## Framework

- Use the `unittest` module for all tests.
- Tests live under `testing/` and mirror `src/` structure.
- Aim for at least 80% test coverage.

## Test Structure

```python
import unittest
from unittest.mock import MagicMock, patch


class TestFeatureName(unittest.TestCase):
    """Tests for feature description."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.client = MagicMock()

    def tearDown(self) -> None:
        """Clean up after tests."""
        pass

    def test_happy_path_returns_expected_result(self) -> None:
        """Test description of what this verifies."""
        # Arrange
        expected = {"id": "123", "status": "created"}
        self.client.create.return_value = expected

        # Act
        result = create_item(self.client, "Test")

        # Assert
        self.assertEqual(result, expected)
        self.client.create.assert_called_once()
```

## Test Coverage

Every new behaviour must include tests covering:

1. **The happy path**: Normal successful operation
2. **At least one edge case**: Boundary conditions, empty inputs, etc.
3. **At least one failure mode**: Error handling, validation failures

## Running Tests

```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run single test file
poetry run python -m unittest testing/path/to/test_file.py

# Run single test method
poetry run python -m unittest testing.path.to.test_file.TestClass.test_method
```

## Mocking

- Use `unittest.mock.patch` for isolating dependencies.
- Mock at the boundary (HTTP calls, database, external APIs).
- Avoid mocking internal implementation details.

```python
@patch("src.notion.client.requests.get")
def test_get_page_returns_page_data(self, mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {"id": "page-123"}
    mock_get.return_value.status_code = 200

    result = self.client.get_page("page-123")

    self.assertEqual(result["id"], "page-123")
```

## Dynamic Enum Testing

When testing code that uses enums representing external picklists (e.g., dropdown fields from external APIs), avoid hardcoding specific enum values:

```python
# Bad: Hardcoded enum values break when external system changes
mock_client.get_page.return_value = {
    "properties": {"Status": {"status": {"name": "To Do"}}}
}

# Good: Dynamic values from actual enums
from testing.api.notion.fixtures import DEFAULT_TASK_STATUS, build_notion_task_page

mock_client.get_page.return_value = build_notion_task_page(status=DEFAULT_TASK_STATUS)
```

### Shared Fixtures Pattern

Create fixture builders that derive values from actual enums:

```python
# testing/fixtures.py
from src.domain.enums import Status, Priority


def first_value(enum_class: type) -> str:
    """Get the first value from an enum class."""
    return next(iter(enum_class)).value


DEFAULT_STATUS = first_value(Status)
DEFAULT_PRIORITY = first_value(Priority)


def build_item_response(
    item_id: str = "item-123",
    status: str | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    """Build a mock item response using actual enum values."""
    return {
        "id": item_id,
        "status": status or DEFAULT_STATUS,
        "priority": priority or DEFAULT_PRIORITY,
    }
```

## setUp and tearDown

- Use `setUp`/`tearDown` for per-test fixtures.
- Use `setUpClass`/`tearDownClass` for expensive shared fixtures.
- Keep fixtures minimal and focused.

## Test Naming

- Use descriptive names: `test_<action>_<condition>_<expected_result>`
- Examples:
  - `test_create_task_with_valid_data_returns_task_id`
  - `test_create_task_with_empty_name_raises_validation_error`
  - `test_query_tasks_with_no_results_returns_empty_list`

## Avoiding Network Calls

- Tests must be deterministic and isolated.
- Mock all external HTTP calls, database connections, and API clients.
- Use dependency injection to make mocking easier.
