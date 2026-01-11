# PRD28: Notion Content Context and Update Improvements

**Status: UP NEXT**
**Created: 2026-01-11**

---

## 1. Overview

This PRD addresses issues with Notion page content management across **all Notion item types**:

- **Tasks** (`/api/notion/tasks/`)
- **Goals** (`/api/notion/goals/`)
- **Reading List Items** (`/api/notion/reading_list/`)
- **Ideas** (`/api/notion/ideas/`)

**Problems:**
1. **Content visibility gap**: The agent cannot effectively answer questions about descriptions/notes without explicit get calls
2. **Content overwriting bug**: When updating notes, existing content is completely replaced instead of intelligently merged
3. **Silent data loss**: Unsupported Notion block types are silently skipped with no warning

The solution gives the LLM full context of existing content before updates, allowing intelligent merge decisions rather than hardcoded append/replace logic.

---

## 2. Problem Statement

### Problem 1: Agent Lacks Content Context for Updates

When a user asks "add some notes to [item]", the agent:
1. Calls `update_*` with only the new notes
2. `build_*_content()` creates fresh content from ONLY the new notes
3. API uses `replace_page_content()` which deletes all existing blocks
4. **Result**: Existing content is lost

**User example**: Asked to add notes to a task, but existing content was removed:
```
Before: "## Notes\nUpdate project template...\n---\nCreated via AI Agent"
After:  "## Notes\nNew note only\n---\nCreated via AI Agent"
```

This affects all item types: tasks, goals, reading list items, and ideas.

### Problem 2: No Error Handling for Manual Page Edits

When users manually edit Notion pages with unsupported block types (images, code blocks, tables, embeds), the `blocks_to_markdown()` function silently skips them with no logging or warning. Users lose content without knowing.

**Unsupported block types that are silently dropped:**
- `image`, `video`, `file`, `pdf`
- `code` (with syntax highlighting)
- `table`, `table_row`
- `quote`, `callout`, `toggle`
- `embed`, `bookmark`, `link_preview`
- `synced_block`, `child_database`, `column_list`

This affects all Notion items since they all use `blocks_to_markdown()` from `src/notion/blocks.py`.

---

## 3. Goals

1. **LLM-driven content merging**: Agent fetches existing content before updates, decides how to merge intelligently
2. **Transparency about unsupported content**: Log and report when block types cannot be converted
3. **Preserve user's manual edits**: Handle edge cases gracefully when page formatting differs from expected structure

## 4. Non-Goals

- Automatic append logic (LLM decides based on context)
- Supporting all Notion block types (focus on logging what's unsupported)
- Changing how `query_tasks` works (intentionally returns limited fields)

---

## 5. Proposed Solution

### 5.1 Require Content Fetch Before Updates

Modify the agent's update workflow to **always fetch existing content** when updating description/notes:

```
User: "Add a note to task X about the meeting"
        ↓
Agent: Calls get_task(task_id) to fetch current content
        ↓
Agent: Sees existing content in context
        ↓
Agent: Constructs merged content (LLM decides how)
        ↓
Agent: Calls update_task with complete new content
```

**Chosen approach: Tool description guidance**
- Update `update_task` tool description to explicitly state: "Before updating content, first call get_task to retrieve existing content and merge appropriately"
- Simple, backwards compatible, relies on LLM following instructions
- Can add stricter enforcement later if needed

### 5.2 Guard Against Unsupported Block Types

**Short-term solution**: If a page contains unsupported block types, **fail the content update** with a clear error message rather than silently losing data.

**Rationale**:
- Prevents silent data loss
- Informs the user they need to manually handle the page in Notion
- Simple to implement
- Can be relaxed later once we support more block types

**Implementation:**

When fetching content for update purposes, check for unsupported blocks and return an error:

```python
# src/notion/blocks.py

class UnsupportedBlockTypeError(Exception):
    """Raised when page contains blocks that cannot be safely converted."""

    def __init__(self, unsupported_types: set[str]) -> None:
        self.unsupported_types = unsupported_types
        types_str = ", ".join(sorted(unsupported_types))
        super().__init__(
            f"Page contains unsupported block types: {types_str}. "
            "Please edit this task directly in Notion to avoid data loss."
        )


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Convert Notion blocks to markdown.

    :param blocks: List of Notion block objects.
    :raises UnsupportedBlockTypeError: If unsupported blocks found.
    """
    unsupported_types: set[str] = set()
    lines: list[str] = []
    counter = 1

    for block in blocks:
        block_type = block.get("type", "")

        if block_type not in SUPPORTED_BLOCK_TYPES:
            unsupported_types.add(block_type)
            logger.warning(
                f"Unsupported block skipped: type={block_type}, id={block.get('id', 'unknown')}"
            )
            continue

        line, counter = _block_to_markdown(block, counter)
        if line is not None:
            lines.append(line)

    if unsupported_types:
        raise UnsupportedBlockTypeError(unsupported_types)

    return "\n".join(lines)
```

**In the update endpoint**, the conversion will now raise if unsupported blocks exist:

```python
# src/api/notion/tasks/endpoints.py

@router.patch("/{task_id}")
def update_task(task_id: str, request: UpdateTaskRequest, ...):
    # Before updating content, check if current page has unsupported blocks
    if request.content is not None:
        existing_blocks = client.get_page_content(task_id)
        try:
            blocks_to_markdown(existing_blocks)  # Raises if unsupported blocks
        except UnsupportedBlockTypeError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            ) from e

    # ... proceed with update
```

### 5.3 Fail on Read with Unsupported Content

When **fetching** task content, also fail if unsupported blocks exist:

```python
# src/api/notion/tasks/endpoints.py

@router.get("/{task_id}")
def get_task(task_id: str, ...) -> TaskResponse:
    # ... fetch task properties ...

    # Fetch and convert content - raises if unsupported blocks
    blocks = client.get_page_content(task_id)
    try:
        markdown = blocks_to_markdown(blocks)
    except UnsupportedBlockTypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    return TaskResponse(..., content=markdown)
```

The agent receives a clear error message:
```json
{
  "detail": "Page contains unsupported block types: code, image. Please edit this task directly in Notion to avoid data loss."
}
```

This ensures the agent knows about the limitation and can inform the user to use Notion directly.

---

## 6. Implementation Details

### 6.1 Update Tool Descriptions (All Item Types)

Update the `update_description` in each tool config to require fetch-before-update:

**Files:**
- `src/agent/tools/tasks.py`
- `src/agent/tools/goals.py`
- `src/agent/tools/reading_list.py`
- `src/agent/tools/ideas.py`

**Pattern for all:**
```python
update_description=(
    "Update an existing [item]. IMPORTANT: Before updating description or notes, "
    "you MUST first call get_[item] to retrieve the current content. Then construct "
    "the complete new content by merging existing content with your changes. "
    "The content field will REPLACE all existing page content, so include "
    "everything that should remain. If the get call fails due to unsupported blocks, "
    "inform the user they must edit directly in Notion."
),
```

### 6.2 Handle Errors in All Endpoints

**Files:**
- `src/api/notion/tasks/endpoints.py`
- `src/api/notion/goals/endpoints.py`
- `src/api/notion/reading_list/endpoints.py`
- `src/api/notion/ideas/endpoints.py`

All get and update endpoints need to catch the error and return 400:

```python
from src.notion.blocks import blocks_to_markdown, UnsupportedBlockTypeError

@router.get("/{item_id}")
def get_item(item_id: str, ...) -> ItemResponse:
    # ... fetch item properties ...

    blocks = client.get_page_content(item_id)
    try:
        markdown = blocks_to_markdown(blocks)
    except UnsupportedBlockTypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ItemResponse(..., content=markdown)


@router.patch("/{item_id}")
def update_item(item_id: str, request: UpdateItemRequest, ...):
    if request.content is not None:
        existing_blocks = client.get_page_content(item_id)
        try:
            blocks_to_markdown(existing_blocks)
        except UnsupportedBlockTypeError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # ... proceed with update
```

---

## 7. Files to Modify

### Core (shared by all item types)

| File | Changes |
|------|---------|
| `src/notion/blocks.py` | Add `UnsupportedBlockTypeError`, raise on unsupported blocks |
| `testing/notion/test_blocks.py` | Add tests for exception on unsupported blocks |

### Agent Tools (update descriptions)

| File | Changes |
|------|---------|
| `src/agent/tools/tasks.py` | Update tool description to require fetch-before-update |
| `src/agent/tools/goals.py` | Update tool description to require fetch-before-update |
| `src/agent/tools/reading_list.py` | Update tool description to require fetch-before-update |
| `src/agent/tools/ideas.py` | Update tool description to require fetch-before-update |

### API Endpoints (catch errors)

| File | Changes |
|------|---------|
| `src/api/notion/tasks/endpoints.py` | Catch `UnsupportedBlockTypeError` in get and update |
| `src/api/notion/goals/endpoints.py` | Catch `UnsupportedBlockTypeError` in get and update |
| `src/api/notion/reading_list/endpoints.py` | Catch `UnsupportedBlockTypeError` in get and update |
| `src/api/notion/ideas/endpoints.py` | Catch `UnsupportedBlockTypeError` in get and update |

### Tests

| File | Changes |
|------|---------|
| `testing/api/notion/test_task_endpoints.py` | Add tests for 400 errors on unsupported blocks |
| `testing/api/notion/test_goal_endpoints.py` | Add tests for 400 errors on unsupported blocks |
| `testing/api/notion/test_reading_list_endpoints.py` | Add tests for 400 errors on unsupported blocks |
| `testing/api/notion/test_idea_endpoints.py` | Add tests for 400 errors on unsupported blocks |

---

## 8. Testing

### Unit Tests (blocks.py)

1. **Test unsupported block raises exception**: `blocks_to_markdown(blocks)` raises `UnsupportedBlockTypeError` when unsupported blocks present
2. **Test supported blocks work**: No exception when all blocks are supported types
3. **Test exception contains block types**: Error message lists the unsupported types found
4. **Test mixed blocks**: Exception raised listing only the unsupported types

### API Tests (all item types)

For each item type (tasks, goals, reading_list, ideas):

1. **Test get fails with unsupported blocks**: GET returns 400 with clear error message
2. **Test update fails with unsupported blocks**: PATCH returns 400 with clear error message
3. **Test get succeeds with supported blocks**: Content returned normally
4. **Test update succeeds with supported blocks**: Content updates work normally

---

## 9. Success Criteria

1. Agent fetches existing content before updating notes/description for all item types (via tool description guidance)
2. Unsupported block types logged at WARNING level with block type and ID
3. **All get and update endpoints fail** when page contains unsupported blocks (400 error)
4. Error message clearly lists which block types are unsupported
5. Agent informs user to edit directly in Notion when unsupported blocks detected
6. Existing content preserved when adding new notes to supported pages (LLM merges intelligently)
7. Changes applied consistently across tasks, goals, reading list items, and ideas

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM ignores fetch-before-update instruction | Monitor behaviour; add parameter enforcement if unreliable |
| User frustration when tasks can't be read/updated | Clear error message explains how to resolve (edit in Notion) |
| Excessive logging for pages with many unsupported blocks | Log summary once per page, not per block |

---

## 11. Future Considerations

- Expand supported block types (code, quote, table)
- Add "append_notes" as explicit tool parameter
- Return unsupported blocks as raw JSON for transparency