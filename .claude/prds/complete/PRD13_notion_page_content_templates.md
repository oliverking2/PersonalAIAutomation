# PRD13: Notion Page Content Support

**Status: PROPOSED**

## Problem Statement

Currently, when tasks/goals/reading items are created via the API, only the page properties are set (title, status, due date, etc.). The page body remains empty. This means:

1. No additional context or description is captured
2. Tasks like "Review Q4 report" have no details about what to review
3. Goals lack success criteria or breakdown of steps
4. Reading items have no notes about why the item was added

## Scope

This PRD covers the **infrastructure** for page content support:
- Markdown-to-Notion blocks conversion
- NotionClient methods for content operations
- API endpoints for content CRUD
- Optional `content` field on create endpoints

Agent tool changes (prompting for details, validation) are covered in **PRD14**.

## Requirements

1. **Markdown to blocks**: Convert markdown text to Notion block objects
2. **Blocks to markdown**: Convert Notion blocks back to readable markdown
3. **NotionClient methods**: `append_blocks()`, `get_blocks()`
4. **Content endpoints**: GET/PUT/POST for page content
5. **Create integration**: Optional `content` field on create requests

## Notion Block Types

We'll support a subset of Notion block types for simplicity:

| Block Type | Markdown | Notes |
|------------|----------|-------|
| `heading_2` | `## Heading` | Section headers |
| `heading_3` | `### Heading` | Sub-sections |
| `paragraph` | Plain text | Regular content |
| `bulleted_list_item` | `- item` | Unordered lists |
| `numbered_list_item` | `1. item` | Ordered lists |
| `to_do` | `- [ ] item` | Checkboxes |
| `divider` | `---` | Horizontal rules |

## Implementation

### New File: `src/notion/blocks.py`

```python
"""Markdown to/from Notion blocks conversion."""

def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """Convert markdown text to Notion block objects.

    :param markdown: Markdown formatted text.
    :returns: List of Notion block objects.
    """
    ...

def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Convert Notion blocks to markdown text.

    :param blocks: List of Notion block objects.
    :returns: Markdown formatted text.
    """
    ...
```

### NotionClient Additions

```python
# src/notion/client.py

def get_page_content(self, page_id: str) -> list[dict[str, Any]]:
    """Get all blocks from a page.

    :param page_id: The Notion page ID.
    :returns: List of block objects.
    """
    ...

def append_page_content(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
    """Append blocks to a page.

    :param page_id: The Notion page ID.
    :param blocks: List of block objects to append.
    """
    ...

def replace_page_content(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
    """Replace all page content with new blocks.

    :param page_id: The Notion page ID.
    :param blocks: List of block objects.
    """
    ...
```

### API Endpoints

```
GET  /notion/pages/{page_id}/content
     Returns: {"blocks": [...], "markdown": "..."}

PUT  /notion/pages/{page_id}/content
     Request: {"markdown": "..."}
     Replaces all content

POST /notion/pages/{page_id}/content
     Request: {"markdown": "..."}
     Appends to existing content
```

### Create Request Updates

Add optional `content` field to create requests:

```python
class TaskCreateRequest(BaseModel):
    task_name: str
    # ... existing fields ...
    content: str | None = Field(None, description="Markdown content for page body")
```

When `content` is provided, convert to blocks and append after page creation.

## Files to Create/Modify

### New Files
- `src/notion/blocks.py` - Markdown ↔ blocks conversion
- `src/api/notion/pages/content.py` - Content endpoints (or add to existing pages/endpoints.py)
- `testing/notion/test_blocks.py` - Block conversion tests

### Modified Files
- `src/notion/client.py` - Add content methods
- `src/api/notion/tasks/models.py` - Add `content` field
- `src/api/notion/tasks/endpoints.py` - Handle content on create
- `src/api/notion/goals/models.py` - Add `content` field
- `src/api/notion/goals/endpoints.py` - Handle content on create
- `src/api/notion/reading_list/models.py` - Add `content` field
- `src/api/notion/reading_list/endpoints.py` - Handle content on create

## Success Criteria

1. Can create pages with content via API
2. Can read page content as markdown
3. Can append/replace page content
4. Block conversion handles common markdown patterns
5. All existing tests pass
