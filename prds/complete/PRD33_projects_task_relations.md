# PRD: Projects with Task-Project Relations

## Overview

Add a Projects database to Notion with full CRUD operations and establish optional relations between Tasks and Projects. This enables grouping related tasks under larger initiatives.

## Requirements

1. **Projects CRUD**: Full create, query, get, update operations for projects
2. **Task-Project linking**: Optional relation field on tasks pointing to a project
3. **Agent behaviour**: Proactively suggest linking tasks to projects when relevant
4. **Relation support**: Add generic relation field type to the parser

---

## Project Model Design

### Fields

| Field | Notion Name | Type | Required | Description |
|-------|-------------|------|----------|-------------|
| `id` | - | str | Yes | Notion page ID |
| `project_name` | Project name | TITLE | Yes | Project title |
| `status` | Status | STATUS | No | Project status |
| `priority` | Priority | SELECT | No | Project priority (separate enum) |
| `project_group` | Project Group | SELECT | Yes | Work/Personal category |
| `due_date` | Due date | DATE | No | Target completion date |

### Enums

**Note**: Project enums are intentionally separate from task enums as Notion picklist values may differ between databases.

```python
class ProjectStatus(StrEnum):
    """Valid status values for projects (may differ from TaskStatus)."""
    NOT_STARTED = "Not started"
    IN_PROGRESS = "In progress"
    ON_HOLD = "On Hold"
    COMPLETED = "Completed"


class ProjectPriority(StrEnum):
    """Valid priority values for projects (may differ from task Priority)."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ProjectGroup(StrEnum):
    """Valid group values for projects (may differ from TaskGroup)."""
    PERSONAL = "Personal"
    WORK = "Work"
```

---

## Implementation Plan

### Phase 1: Foundation

**1. Add enums** (`src/notion/enums.py`)
- Add `ProjectStatus`, `ProjectPriority`, and `ProjectGroup` enums
- Keep separate from task enums to allow Notion picklist values to vary independently

**2. Add RELATION field type** (`src/notion/parser.py`)
- Add `RELATION = "relation"` to `FieldType` enum
- Add extraction function:
  ```python
  def _extract_single_relation(prop: dict[str, Any]) -> str | None:
      relation = prop.get("relation", [])
      return relation[0].get("id") if relation else None
  ```
- Add build handling in `_build_property`:
  ```python
  case FieldType.RELATION:
      if isinstance(value, str):
          return {field.notion_name: {"relation": [{"id": value}]}}
      return {field.notion_name: {"relation": [{"id": v} for v in value]}}
  ```

**3. Add NotionProject model** (`src/notion/models.py`)
- Create `NotionProject` Pydantic model with fields above

**4. Add PROJECT_FIELDS registry** (`src/notion/parser.py`)
- Add field registry and `build_project_properties()`, `parse_page_to_project()` functions

### Phase 2: Projects API

**5. Create API directory** (`src/api/notion/projects/`)
- `__init__.py` - Export router
- `models.py` - Request/response models
- `endpoints.py` - CRUD endpoints (follow goals/tasks pattern)

**6. Add dependency** (`src/api/notion/dependencies.py`)
- Add `get_projects_data_source_id()` function

**7. Register router** (`src/api/notion/router.py`)
- Include projects router

**8. Update environment** (`.env_example`)
- Add `NOTION_PROJECTS_DATA_SOURCE_ID`

### Phase 3: Agent Tools for Projects

**9. Add agent args** (`src/agent/tools/models.py`)
- `AgentProjectCreateArgs` - project_name, description, notes, project_group, status, priority, due_date
- `AgentProjectUpdateArgs` - all fields optional

**10. Add content template** (`src/agent/utils/templates.py`)
- `build_project_content()` function for description/notes markdown

**11. Create project tools** (`src/agent/tools/projects.py`)
- Use `CRUDToolConfig` factory pattern
- Generate query_projects, get_project, create_projects, update_project tools

**12. Register tools** (`src/agent/tools/__init__.py`)
- Export `get_projects_tools`

### Phase 4: Task-Project Linking

**13. Update NotionTask model** (`src/notion/models.py`)
- Add `project_id: str | None` field

**14. Update TASK_FIELDS** (`src/notion/parser.py`)
- Add `"project_id": TaskField("Project", FieldType.RELATION)`
- Update `parse_page_to_task()` to extract relation

**15. Update task API models** (`src/api/notion/tasks/models.py`)
- Add `project_id` to `TaskResponse`, `TaskCreateRequest`, `TaskUpdateRequest`, `TaskQueryRequest`

**16. Update task endpoints** (`src/api/notion/tasks/endpoints.py`)
- Add project_id to property building
- Add relation filter for `project_id` in query

**17. Update agent task args** (`src/agent/tools/models.py`)
- Add `project_id` field to `AgentTaskCreateArgs` and `AgentTaskUpdateArgs`

### Phase 5: Agent Behaviour

**18. Update task tool descriptions** (`src/agent/tools/tasks.py`)
- Add guidance about suggesting project linking when tasks appear to be part of larger initiatives

### Phase 6: Testing

**19. Write tests for:**
- Relation field parsing and building (`testing/notion/test_parser.py`)
- Project CRUD operations (`testing/api/notion/projects/`)
- Task-project linking
- Agent project tools

---

## Critical Files to Modify

| File | Changes |
|------|---------|
| `src/notion/enums.py` | Add `ProjectStatus`, `ProjectPriority`, `ProjectGroup` |
| `src/notion/models.py` | Add `NotionProject`, update `NotionTask` with `project_id` |
| `src/notion/parser.py` | Add `RELATION` field type, `PROJECT_FIELDS`, extraction/build functions |
| `src/api/notion/projects/` | New directory - endpoints.py, models.py, __init__.py |
| `src/api/notion/dependencies.py` | Add `get_projects_data_source_id()` |
| `src/api/notion/router.py` | Register projects router |
| `src/api/notion/tasks/models.py` | Add `project_id` to all models |
| `src/api/notion/tasks/endpoints.py` | Handle project_id in create/update/query |
| `src/agent/tools/models.py` | Add project args, update task args |
| `src/agent/tools/projects.py` | New file - project tool config |
| `src/agent/tools/tasks.py` | Update descriptions for project suggestions |
| `src/agent/utils/templates.py` | Add `build_project_content()` |
| `.env_example` | Add `NOTION_PROJECTS_DATA_SOURCE_ID` |

---

## Notion Setup Required

Before implementation, create in Notion:

1. **Projects database** with properties:
   - Project name (Title)
   - Status (Status: Not started, In progress, On Hold, Completed)
   - Priority (Select: High, Medium, Low)
   - Project Group (Select: Personal, Work)
   - Due date (Date)

2. **Add relation to Tasks database**:
   - Add "Project" relation property pointing to Projects database
   - Configure as single-select relation (one project per task)

---

## Verification

1. **API tests**: `make test` passes with new project endpoints
2. **Type checking**: `make types` passes
3. **Lint/format**: `make check` passes
4. **Manual testing**:
   - Create a project via API
   - Create a task linked to the project
   - Query tasks filtered by project_id
   - Query projects via agent tools
   - Verify agent suggests project linking when creating related tasks

---

## Agent Behaviour Notes

The agent should suggest project linking when:
- Task name suggests it's part of a larger effort (e.g., "Build login page", "Design database schema")
- User mentions a project name that matches an existing project
- Multiple related tasks are being created in sequence

The agent should NOT suggest project linking when:
- Task is clearly standalone (e.g., "Buy milk", "Call dentist")
- User explicitly says the task is not part of a project
