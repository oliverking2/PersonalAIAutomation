# PRD13: Notion Page Content Templates

**Status: PROPOSED**

## Problem Statement

Currently, when tasks/goals/reading items are created via the agent, only the page properties are set (title, status, due date, etc.). The page body remains empty. This means:

1. No additional context or description is captured
2. Tasks like "Review Q4 report" have no details about what to review or why
3. Goals lack success criteria or breakdown of steps
4. Reading items have no notes about why the item was added

Users lose context when they return to items weeks later.

## Requirements

1. **Page content support**: API should support reading and writing page body content (not just properties)
2. **Domain-specific templates**: Each domain (tasks, goals, reading list) should have a default template structure
3. **Agent prompting**: Agent should gather necessary details to populate the template before creating
4. **Template sections**: Templates should have logical sections (e.g., Description, Acceptance Criteria, Notes)
5. **Append/Update**: Support both setting initial content and appending to existing content

## Proposed Templates

### Task Template
```markdown
## Description
{What needs to be done and why}

## Acceptance Criteria
- [ ] {Criterion 1}
- [ ] {Criterion 2}

## Notes
{Any additional context, links, or references}

---
Created via AI Agent on {date}
```

### Goal Template
```markdown
## Description
{What this goal aims to achieve}

## Success Criteria
- [ ] {How will we know this is complete?}

## Key Results
- {Measurable outcome 1}
- {Measurable outcome 2}

## Notes
{Context, motivation, or related goals}

---
Created via AI Agent on {date}
```

### Reading List Template
```markdown
## Why Read This
{Reason for adding to reading list}

## Key Topics
- {Topic 1}
- {Topic 2}

## Notes
{Any notes or takeaways after reading}

---
Added via AI Agent on {date}
```

## API Changes

### New Endpoints

```python
# Get page content (body blocks)
GET /notion/pages/{page_id}/content
Response: {"blocks": [...], "plain_text": "..."}

# Set page content (replace body)
PUT /notion/pages/{page_id}/content
Request: {"markdown": "..."}  # or {"blocks": [...]}

# Append to page content
POST /notion/pages/{page_id}/content
Request: {"markdown": "..."}
```

### Modified Create Endpoints

Add optional `content` field to create requests:

```python
class TaskCreateRequest(BaseModel):
    task_name: str
    # ... existing fields ...
    content: str | None = Field(None, description="Markdown content for page body")

class GoalCreateRequest(BaseModel):
    goal_name: str
    # ... existing fields ...
    content: str | None = Field(None, description="Markdown content for page body")

class ReadingItemCreateRequest(BaseModel):
    title: str
    # ... existing fields ...
    content: str | None = Field(None, description="Markdown content for page body")
```

## Notion API Integration

Notion uses blocks for page content. We'll need to:

1. **Convert markdown to blocks**: Parse markdown into Notion block objects
2. **Convert blocks to markdown**: For reading content back
3. **Use Notion's append children API**: `PATCH /v1/blocks/{page_id}/children`

### Block Types Needed
- `paragraph` - Regular text
- `heading_2`, `heading_3` - Section headers
- `bulleted_list_item` - List items
- `to_do` - Checkboxes
- `divider` - Horizontal rule

## Agent Tool Changes

### Updated Tool Descriptions

```python
ToolDef(
    name="create_task",
    description=(
        "Create a new task. Requires a descriptive task name, task group, and due date. "
        "IMPORTANT: Before creating, ask the user for: "
        "1) What needs to be done (description) "
        "2) How will you know it's complete (acceptance criteria) "
        "Pass these as the 'content' parameter using the template format."
    ),
    # ...
)
```

### Template Helper

```python
def build_task_content(
    description: str,
    acceptance_criteria: list[str],
    notes: str | None = None,
) -> str:
    """Build markdown content for a task page."""
    lines = [
        "## Description",
        description,
        "",
        "## Acceptance Criteria",
    ]
    for criterion in acceptance_criteria:
        lines.append(f"- [ ] {criterion}")

    if notes:
        lines.extend(["", "## Notes", notes])

    lines.extend(["", "---", f"Created via AI Agent on {date.today()}"])
    return "\n".join(lines)
```

## Integration with AGENT-003 (Tool Factory)

This PRD affects tool structure, so consider implementing alongside AGENT-003:

```python
def create_crud_tools(
    domain: str,
    endpoint_prefix: str,
    query_model: type[BaseModel],
    create_model: type[BaseModel],
    update_model: type[BaseModel],
    content_template: ContentTemplate | None = None,  # NEW
    enum_fields: dict[str, type[StrEnum]],
) -> list[ToolDef]:
    """Generate CRUD tools with optional content template support."""
```

The factory could:
1. Generate content builder functions from templates
2. Add content-related tool descriptions
3. Handle markdown-to-blocks conversion uniformly

## Agent Workflow Example

```
User: "Create a task to review the Q4 report"

Agent: "I'll create that task. To make it useful when you come back to it:
1. What specifically should you review in the Q4 report?
2. How will you know you're done?"

User: "Check the revenue numbers match the projections and flag any discrepancies over 5%. Done when I've added comments to the shared doc."

Agent: Creates task with:
- Name: "Review Q4 report - verify revenue vs projections"
- Content:
  ## Description
  Review the Q4 report focusing on revenue numbers. Compare against
  projections and identify any discrepancies.

  ## Acceptance Criteria
  - [ ] Reviewed all revenue line items
  - [ ] Flagged discrepancies over 5%
  - [ ] Added comments to shared doc
```

## Files to Modify

### New Files
- `src/notion/blocks.py` - Markdown to/from Notion blocks conversion
- `src/api/notion/content/` - Content endpoints

### Modified Files
- `src/api/notion/tasks/models.py` - Add `content` field
- `src/api/notion/tasks/endpoints.py` - Handle content on create
- `src/api/notion/goals/models.py` - Add `content` field
- `src/api/notion/goals/endpoints.py` - Handle content on create
- `src/api/notion/reading_list/models.py` - Add `content` field
- `src/api/notion/reading_list/endpoints.py` - Handle content on create
- `src/notion/client.py` - Add `append_blocks()` method
- `src/agent/tools/*.py` - Update tool descriptions, add content helpers

## Implementation Phases

### Phase 1: API Foundation
1. Implement markdown-to-blocks converter
2. Add `append_blocks()` to NotionClient
3. Create content endpoints (GET, PUT, POST)

### Phase 2: Create Integration
4. Add `content` field to create request models
5. Update create endpoints to handle content
6. Add content helpers/builders

### Phase 3: Agent Integration
7. Update tool descriptions to prompt for details
8. Add template builder functions to tools
9. Test end-to-end workflow

### Phase 4: AGENT-003 Integration (Optional)
10. Combine with tool factory refactor
11. Centralise content template configuration

## Success Criteria

1. Agent asks clarifying questions before creating tasks/goals
2. Created pages have structured content, not empty bodies
3. Users can find and understand tasks weeks later
4. Content is viewable/editable in Notion normally
5. Templates are domain-specific and useful

## Future Considerations

- **Custom templates**: User-defined templates per task group or category
- **Smart defaults**: Pre-fill acceptance criteria based on task type
- **Content extraction**: Parse content from user messages automatically
- **Reading notes**: Prompt for notes when marking reading item as complete
