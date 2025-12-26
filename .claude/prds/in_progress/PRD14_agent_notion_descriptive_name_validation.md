# PRD14: Agent Quality Prompts for Tasks and Goals

**Status: PROPOSED**

**Depends on**: PRD13 (Page Content Support) - for content field on create requests

## Problem Statement

When users create tasks or goals via the agent, they often:
1. Use vague or ambiguous names ("email task", "meeting", "fix the bug")
2. Provide no additional context or description
3. Skip acceptance criteria or success metrics

These items become meaningless when revisited weeks later. The agent should act as a helpful assistant that prompts for better details before creating items.

## Scope

This PRD covers **agent-side improvements**:
- Name validation logic
- Prompting for descriptive names
- Prompting for page content (descriptions, acceptance criteria)
- Tool description updates
- Template helper functions

Infrastructure (API content support) is covered in **PRD13**.

## Requirements

1. **Name validation**: Detect vague or ambiguous names before creation
2. **Clarification prompts**: Ask for better names when needed
3. **Content prompts**: Ask for description/acceptance criteria
4. **Template builders**: Generate structured page content
5. **Override capability**: Allow users to proceed if they insist

## Part 1: Name Validation

### Vague Name Indicators

| Rule | Examples | Threshold |
|------|----------|-----------|
| Too short | "task", "email" | < 15 characters |
| Common vague words | "thing", "stuff", "item" | Word in blocklist |
| Missing context | "meeting", "review" | Single generic noun/verb |

### Blocklist Words

```python
VAGUE_WORDS = {
    "task", "thing", "stuff", "item", "work", "project",
    "meeting", "email", "call", "review", "fix", "check",
    "update", "do", "finish", "complete", "prep", "prepare",
}
```

### Validation Logic

```python
# src/agent/validation.py

from dataclasses import dataclass
from enum import StrEnum

class ValidationReason(StrEnum):
    TOO_SHORT = "too_short"
    VAGUE_WORDS = "vague_words"

@dataclass(frozen=True)
class NameValidation:
    is_valid: bool
    reason: ValidationReason | None = None
    suggestion: str | None = None

MIN_NAME_LENGTH = 15
MIN_SPECIFIC_WORDS = 2

def validate_name(name: str) -> NameValidation:
    """Validate that a name is descriptive enough.

    :param name: The proposed name.
    :returns: Validation result with suggestion if invalid.
    """
    if len(name) < MIN_NAME_LENGTH:
        return NameValidation(
            is_valid=False,
            reason=ValidationReason.TOO_SHORT,
            suggestion=f"'{name}' is quite short. Can you add more detail?",
        )

    words = set(name.lower().split())
    non_vague = words - VAGUE_WORDS
    if len(non_vague) < MIN_SPECIFIC_WORDS:
        return NameValidation(
            is_valid=False,
            reason=ValidationReason.VAGUE_WORDS,
            suggestion=f"'{name}' is a bit vague. What specifically needs to be done?",
        )

    return NameValidation(is_valid=True)
```

## Part 2: Content Prompts and Templates

### Template Builders

```python
# src/agent/templates.py

from datetime import date

def build_task_content(
    description: str,
    acceptance_criteria: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """Build markdown content for a task page.

    :param description: What needs to be done and why.
    :param acceptance_criteria: List of completion criteria.
    :param notes: Additional context or references.
    :returns: Formatted markdown string.
    """
    lines = ["## Description", description, ""]

    if acceptance_criteria:
        lines.append("## Acceptance Criteria")
        for criterion in acceptance_criteria:
            lines.append(f"- [ ] {criterion}")
        lines.append("")

    if notes:
        lines.extend(["## Notes", notes, ""])

    lines.extend(["---", f"Created via AI Agent on {date.today()}"])
    return "\n".join(lines)


def build_goal_content(
    description: str,
    success_criteria: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """Build markdown content for a goal page."""
    lines = ["## Description", description, ""]

    if success_criteria:
        lines.append("## Success Criteria")
        for criterion in success_criteria:
            lines.append(f"- [ ] {criterion}")
        lines.append("")

    if notes:
        lines.extend(["## Notes", notes, ""])

    lines.extend(["---", f"Created via AI Agent on {date.today()}"])
    return "\n".join(lines)


def build_reading_item_content(notes: str | None = None) -> str:
    """Build markdown content for a reading list item."""
    lines = ["## Notes"]
    if notes:
        lines.append(notes)
    else:
        lines.append("(Add notes after reading)")

    lines.extend(["", "---", f"Added via AI Agent on {date.today()}"])
    return "\n".join(lines)
```

## Part 3: Tool Updates

### Content Access

Page content (in markdown format) is available via the `content` field on responses:
- **GET** (`get_task`, `get_goal`, `get_reading_item`): Returns full page content
- **CREATE** (`create_task`, `create_goal`, `create_reading_item`): Returns the content that was set
- **UPDATE** (`update_task`, `update_goal`, `update_reading_item`): Can replace content; returns current content

**Note**: Query endpoints (`query_tasks`, `query_goals`, `query_reading_list`) do **NOT** return content as this would require fetching content for every item (too expensive). Use the GET endpoint if you need an item's content.

### Content Update Behaviour

When updating an item:
- If `content` is provided in the update request, it **replaces** all existing page content
- If `content` is not provided (or null), existing content is **preserved unchanged**
- Content-only updates are allowed (no properties required)

### Updated Tool Descriptions

Tool descriptions MUST be updated to inform the agent about content capabilities:

1. **GET tools** should mention: "Returns page content in the `content` field (markdown format)"
2. **CREATE tools** should mention: "Include `content` parameter for page body (description, criteria, notes)"
3. **UPDATE tools** should mention: "Include `content` parameter to replace page body; omit to keep existing content"
4. **QUERY tools** should mention: "Does not return content; use GET endpoint to retrieve an item's content"

Example tool descriptions to guide the agent:

```python
# Tasks
ToolDef(
    name="create_task",
    description=(
        "Create a new task. Requires a DESCRIPTIVE name (15+ chars), task group, and due date. "
        "BEFORE creating: "
        "1) Ensure name is specific (not 'email task' or 'meeting') "
        "2) Ask what needs to be done (for description) "
        "3) Ask how they'll know it's complete (for acceptance criteria) "
        "Use build_task_content() to create the content parameter. "
        "If validation fails, needs_clarification=True is returned - ask for more detail."
    ),
)

# Goals
ToolDef(
    name="create_goal",
    description=(
        "Create a new goal. Requires a DESCRIPTIVE name (15+ chars). "
        "BEFORE creating: "
        "1) Ensure name is specific (not 'fitness goal' or 'work stuff') "
        "2) Ask what this goal aims to achieve (for description) "
        "3) Ask how they'll measure success (for success criteria) "
        "Use build_goal_content() to create the content parameter."
    ),
)

# Reading List
ToolDef(
    name="create_reading_item",
    description=(
        "Add an item to the reading list. Requires a title. "
        "Optionally ask why they want to read it (for notes). "
        "Use build_reading_item_content() to create the content parameter."
    ),
)
```

### Tool Handler Changes

Tools should validate names and return `needs_clarification` when invalid:

```python
def create_task(args: TaskCreateRequest) -> dict[str, Any]:
    """Create a new task via API."""
    # Validate name first
    validation = validate_name(args.task_name)
    if not validation.is_valid:
        return {
            "needs_clarification": True,
            "reason": validation.reason,
            "suggestion": validation.suggestion,
            "original_name": args.task_name,
        }

    # Proceed with creation
    with _get_client() as client:
        response = client.post(...)
    return {"item": response, "created": True}
```

## Agent Workflow Examples

### Task with Vague Name
```
User: "Create a task to fix the bug"

Tool: validate_name("fix the bug") → is_valid=False, reason=TOO_SHORT

Agent: "I'd like to create a more specific task so you can find it later.
Which bug are you referring to? For example:
- 'Fix login timeout bug in auth module'
- 'Fix CSS alignment bug on dashboard'"

User: "The null pointer in payment service"

Agent: "Got it. And how will you know when it's fixed?"

User: "When the tests pass and there are no NPEs in the logs"

Agent: Creates task:
- Name: "Fix null pointer exception in payment service"
- Content:
  ## Description
  Fix the null pointer exception occurring in the payment service.

  ## Acceptance Criteria
  - [ ] All tests pass
  - [ ] No NPEs in production logs
```

### Task with Good Name
```
User: "Create a task to review Sarah's Q4 budget proposal by Friday"

Agent: "I'll create that. Anything specific you need to check in the proposal?"

User: "Just make sure the numbers add up"

Agent: Creates task:
- Name: "Review Sarah's Q4 budget proposal"
- Due: Friday
- Content:
  ## Description
  Review the Q4 budget proposal from Sarah.

  ## Acceptance Criteria
  - [ ] Verify numbers add up correctly
```

### User Override
```
User: "Just create a task called 'meeting'"

Agent: "That name is quite vague - you might not remember which meeting later.
Would you like to add more detail, or should I create it as-is?"

User: "Create it as-is"

Agent: Creates task "meeting" (respects user preference)
```

## Files to Create/Modify

### New Files
- `src/agent/validation.py` - Name validation logic
- `src/agent/templates.py` - Content template builders
- `testing/agent/test_validation.py` - Validation tests
- `testing/agent/test_templates.py` - Template tests

### Modified Files
- `src/agent/tools/tasks.py` - Add validation, update descriptions
- `src/agent/tools/goals.py` - Add validation, update descriptions
- `src/agent/tools/reading_list.py` - Update descriptions
- `src/agent/tools/factory.py` - Consider adding validation hook to factory

## Success Criteria

1. Agent prompts for clarification on vague names
2. Agent asks for description/criteria before creating
3. Created pages have structured content (not empty)
4. Users can override and create with minimal info if desired
5. Tool descriptions guide agent behaviour effectively
6. Validation adds no noticeable latency
