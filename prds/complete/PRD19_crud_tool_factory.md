# PRD19: Generic CRUD Tool Factory

**Status: COMPLETE**

**Roadmap Reference**: AGENT-003 (High Priority)

**Related**: PRD13 (Page Content Templates) - Consider implementing together

## Overview

Create a generic tool factory that generates CRUD (Create, Read, Update, Delete/Query) tools from configuration, eliminating ~180 lines of duplicated code across task, goal, and reading list tools.

## Problem Statement

Three tool files have nearly identical patterns:

| File | Lines | Pattern |
|------|-------|---------|
| `tools/tasks.py` | ~60 | `_get_client()`, `query_tasks()`, `get_task()`, `create_task()`, `update_task()` |
| `tools/goals.py` | ~60 | `_get_client()`, `query_goals()`, `get_goal()`, `create_goal()`, `update_goal()` |
| `tools/reading_list.py` | ~60 | `_get_client()`, `query_reading_list()`, `get_reading_list_item()`, etc. |

**Issues**:
1. ~180 lines of duplicated boilerplate
2. Adding a new domain requires copying all patterns
3. Bug fixes must be applied in three places
4. Inconsistencies creep in over time
5. Tool descriptions follow identical template

## Proposed Solution

Create a factory function that generates all CRUD tools from a domain configuration:

```python
# src/agent/tools/factory.py

from dataclasses import dataclass
from typing import Any, Callable
from enum import StrEnum
from pydantic import BaseModel

from src.agent.tools.types import ToolDef
from src.agent.api_client import AgentAPIClient


@dataclass
class CRUDToolConfig:
    """Configuration for generating CRUD tools for a domain."""

    # Domain identification
    domain: str                    # e.g., "task", "goal", "reading_list_item"
    domain_plural: str             # e.g., "tasks", "goals", "reading_list_items"
    endpoint_prefix: str           # e.g., "/notion/tasks"

    # Pydantic models for request/response
    query_model: type[BaseModel]   # e.g., TaskQueryRequest
    create_model: type[BaseModel]  # e.g., TaskCreateRequest
    update_model: type[BaseModel]  # e.g., TaskUpdateRequest
    response_model: type[BaseModel]  # e.g., TaskResponse

    # Field metadata for descriptions
    enum_fields: dict[str, type[StrEnum]]  # e.g., {"status": TaskStatus, "priority": Priority}

    # Optional customisation
    query_description: str | None = None
    create_description: str | None = None
    name_field: str = "name"       # Field used for fuzzy search


def create_crud_tools(config: CRUDToolConfig) -> list[ToolDef]:
    """Generate query/get/create/update tools for a domain.

    :param config: Domain configuration.
    :returns: List of tool definitions for the domain.
    """
    return [
        _create_query_tool(config),
        _create_get_tool(config),
        _create_create_tool(config),
        _create_update_tool(config),
    ]
```

## Tool Generation Implementation

### Query Tool

```python
def _create_query_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate query tool for a domain."""

    def query_handler(input_data: dict[str, Any]) -> dict[str, Any]:
        client = _get_shared_client()
        response = client.post(
            f"{config.endpoint_prefix}/query",
            json=input_data,
        )
        return response.json()

    # Build description with enum values
    enum_hints = _format_enum_hints(config.enum_fields)
    description = config.query_description or (
        f"Query {config.domain_plural} from the tracker. "
        f"Use name_filter for fuzzy search by {config.domain} name. "
        f"Response includes fuzzy_match_quality ('good' or 'weak') when filtering. "
        f"{enum_hints}"
    )

    return ToolDef(
        name=f"query_{config.domain_plural}",
        description=description,
        handler=query_handler,
        input_schema=config.query_model.model_json_schema(),
    )


def _create_get_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate get-by-ID tool for a domain."""

    def get_handler(input_data: dict[str, Any]) -> dict[str, Any]:
        client = _get_shared_client()
        page_id = input_data["page_id"]
        response = client.get(f"{config.endpoint_prefix}/{page_id}")
        return response.json()

    return ToolDef(
        name=f"get_{config.domain}",
        description=f"Get a specific {config.domain} by its page ID.",
        handler=get_handler,
        input_schema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": f"The Notion page ID of the {config.domain}",
                }
            },
            "required": ["page_id"],
        },
    )


def _create_create_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate create tool for a domain."""

    def create_handler(input_data: dict[str, Any]) -> dict[str, Any]:
        client = _get_shared_client()
        response = client.post(
            f"{config.endpoint_prefix}/",
            json=input_data,
        )
        return response.json()

    enum_hints = _format_enum_hints(config.enum_fields)
    description = config.create_description or (
        f"Create a new {config.domain}. {enum_hints}"
    )

    return ToolDef(
        name=f"create_{config.domain}",
        description=description,
        handler=create_handler,
        input_schema=config.create_model.model_json_schema(),
    )


def _create_update_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate update tool for a domain."""

    def update_handler(input_data: dict[str, Any]) -> dict[str, Any]:
        client = _get_shared_client()
        page_id = input_data.pop("page_id")
        response = client.patch(
            f"{config.endpoint_prefix}/{page_id}",
            json=input_data,
        )
        return response.json()

    enum_hints = _format_enum_hints(config.enum_fields)

    return ToolDef(
        name=f"update_{config.domain}",
        description=f"Update an existing {config.domain}. {enum_hints}",
        handler=update_handler,
        input_schema=config.update_model.model_json_schema(),
    )
```

### Helper Functions

```python
def _format_enum_hints(enum_fields: dict[str, type[StrEnum]]) -> str:
    """Format enum field values for tool description."""
    if not enum_fields:
        return ""

    hints = []
    for field_name, enum_class in enum_fields.items():
        values = ", ".join(f"'{v.value}'" for v in enum_class)
        hints.append(f"{field_name}: {values}")

    return "Valid values: " + "; ".join(hints) + "."
```

## Usage Example

```python
# src/agent/tools/tasks.py (simplified)

from src.agent.tools.factory import create_crud_tools, CRUDToolConfig
from src.api.notion.tasks.models import (
    TaskQueryRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskResponse,
)
from src.notion.enums import TaskStatus, Priority


TASK_TOOL_CONFIG = CRUDToolConfig(
    domain="task",
    domain_plural="tasks",
    endpoint_prefix="/notion/tasks",
    query_model=TaskQueryRequest,
    create_model=TaskCreateRequest,
    update_model=TaskUpdateRequest,
    response_model=TaskResponse,
    enum_fields={
        "status": TaskStatus,
        "priority": Priority,
    },
)


def get_task_tools() -> list[ToolDef]:
    """Get all task-related tools."""
    return create_crud_tools(TASK_TOOL_CONFIG)
```

## File Structure

```
src/agent/tools/
├── __init__.py
├── factory.py          # NEW: CRUDToolConfig, create_crud_tools()
├── registry.py         # Updated to use factory
├── tasks.py            # Simplified: just config + get_task_tools()
├── goals.py            # Simplified: just config + get_goal_tools()
└── reading_list.py     # Simplified: just config + get_reading_list_tools()
```

## Migration Steps

1. Create `src/agent/tools/factory.py` with `CRUDToolConfig` and `create_crud_tools()`
2. Add helper functions (`_get_shared_client`, `_format_enum_hints`)
3. Update `tasks.py` to use factory pattern
4. Update `goals.py` to use factory pattern
5. Update `reading_list.py` to use factory pattern
6. Update tool registry to collect tools from all domains
7. Remove duplicated code from individual tool files
8. Write unit tests for factory functions
9. Run integration tests to verify tool behaviour unchanged

## Benefits

1. **DRY**: ~180 lines reduced to ~30 lines per domain
2. **Consistency**: All domains follow identical patterns
3. **Extensibility**: New domain = new config object only
4. **Maintainability**: Bug fixes in one place

## Adding a New Domain

After implementation, adding a new domain (e.g., Projects) requires only:

```python
# src/agent/tools/projects.py

PROJECT_TOOL_CONFIG = CRUDToolConfig(
    domain="project",
    domain_plural="projects",
    endpoint_prefix="/notion/projects",
    query_model=ProjectQueryRequest,
    create_model=ProjectCreateRequest,
    update_model=ProjectUpdateRequest,
    response_model=ProjectResponse,
    enum_fields={"status": ProjectStatus},
)

def get_project_tools() -> list[ToolDef]:
    return create_crud_tools(PROJECT_TOOL_CONFIG)
```

## Testing

```python
class TestCRUDToolFactory(unittest.TestCase):
    def test_creates_four_tools(self):
        """Test factory creates query, get, create, update tools."""
        config = CRUDToolConfig(
            domain="task",
            domain_plural="tasks",
            endpoint_prefix="/notion/tasks",
            query_model=TaskQueryRequest,
            create_model=TaskCreateRequest,
            update_model=TaskUpdateRequest,
            response_model=TaskResponse,
            enum_fields={},
        )

        tools = create_crud_tools(config)

        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"query_tasks", "get_task", "create_task", "update_task"})

    def test_enum_hints_included_in_description(self):
        """Test enum values appear in tool descriptions."""
        config = CRUDToolConfig(
            domain="task",
            domain_plural="tasks",
            endpoint_prefix="/notion/tasks",
            query_model=TaskQueryRequest,
            create_model=TaskCreateRequest,
            update_model=TaskUpdateRequest,
            response_model=TaskResponse,
            enum_fields={"status": TaskStatus},
        )

        tools = create_crud_tools(config)
        query_tool = next(t for t in tools if t.name == "query_tasks")

        self.assertIn("In Progress", query_tool.description)
        self.assertIn("Done", query_tool.description)
```

## Success Criteria

1. All three domain tool files use factory pattern
2. No duplicated CRUD logic across files
3. Adding new domain requires only config object
4. All existing tool tests pass unchanged
5. Tool descriptions remain accurate and helpful
