# PRD12: Fuzzy Name Search for Query Tools

**Status: IMPLEMENTED**

## Problem Statement

When users want to update tasks/goals/reading items, they refer to them by approximate names ("the email task", "calendar cleanup") but the update tools require exact IDs. Currently:

1. Agent asks user for ID
2. User doesn't know the ID
3. Query tools return all items (50+), which is too much context
4. No way to narrow down results by name

## Requirements

1. **Fuzzy name matching**: Query tools should accept a `name_filter` parameter that uses fuzzy matching (rapidfuzz)
2. **Result limiting**: Return top 5 matches above a relevance threshold
3. **Fallback behaviour**: If no matches above threshold, return top 5 by any score with a `fuzzy_match_quality: "weak"` indicator
4. **Default status filter**: Query should default to non-complete items via boolean flags, with visibility in response
5. **Apply to all domains**: Tasks, Goals, Reading List

## Proposed Changes

### API Layer

Add to query request models:
```python
class TaskQueryRequest(BaseModel):
    name_filter: str | None = None  # Fuzzy match against task name
    include_done: bool = False  # Whether to include completed tasks (default: exclude)
    # ... existing fields ...

class GoalQueryRequest(BaseModel):
    name_filter: str | None = None
    include_complete: bool = False
    # ...

class ReadingListQueryRequest(BaseModel):
    name_filter: str | None = None
    include_read: bool = False
    # ...
```

Add to query response models:
```python
class TaskQueryResponse(BaseModel):
    results: list[TaskResponse]
    fuzzy_match_quality: Literal["good", "weak"] | None = None
    # None = no name_filter provided (unfiltered results)
    # "good" = best match score >= 60
    # "weak" = no matches above threshold, showing best guesses
    excluded_done: bool = False  # True if completed items were excluded from results
```

**Note on `fuzzy_match_quality`**: This reflects the confidence of the **best candidate**, not per-item quality. If per-item scores are needed in future, they would be added as a separate field to avoid breaking this contract.

Modify query endpoints to:
1. If `name_filter` provided, use rapidfuzz to score results
2. Return top 5 matches above threshold (score >= 60) with `quality="good"`
3. If no matches above threshold, return top 5 by any score with `quality="weak"`
4. If no `name_filter`, return `quality=None` (unfiltered)

### Dependencies

Add `rapidfuzz` to project:
```bash
poetry add rapidfuzz
```

### Fuzzy Matching Logic

Location: `src/api/notion/common/utils.py`

```python
from typing import Literal

from rapidfuzz import fuzz

FuzzyMatchQuality = Literal["good", "weak"]

# Minimum token length to include in matching (filters "the", "a", "to", etc.)
MIN_TOKEN_LENGTH = 3

def filter_by_fuzzy_name(
    items: list[dict],
    name_filter: str,
    name_field: str = "name",
    limit: int = 5,
) -> tuple[list[dict], FuzzyMatchQuality]:
    """Filter items by fuzzy name match.

    Uses partial_ratio on the full name string. This is Phase 1 matching.
    Token-based or weighted matching may be added if false positives become common.

    :param items: List of items with a name field.
    :param name_filter: Search term.
    :param name_field: Field name containing the item name (e.g., "task_name").
    :param limit: Maximum results to return.
    :returns: Tuple of (filtered items, match quality).
    """
    if not name_filter:
        return items[:limit], None  # type: ignore[return-value]

    # Normalise and strip short tokens from search term
    tokens = name_filter.lower().split()
    filtered_tokens = [t for t in tokens if len(t) >= MIN_TOKEN_LENGTH]
    normalised_filter = " ".join(filtered_tokens) if filtered_tokens else name_filter.lower()

    scored = [
        (item, fuzz.partial_ratio(normalised_filter, item[name_field].lower()))
        for item in items
    ]

    # Filter by threshold and sort by score
    threshold = 60
    matches = [(item, score) for item, score in scored if score >= threshold]
    matches.sort(key=lambda x: x[1], reverse=True)

    if matches:
        return [item for item, _ in matches[:limit]], "good"

    # No good matches - return top by any score
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in scored[:limit]], "weak"
```

### Default Status Filter

Add boolean flags to exclude completed items by default:

| Domain       | Request Flag         | Response Flag      | Default | Excludes            |
|--------------|---------------------|-------------------|---------|---------------------|
| Tasks        | `include_done`      | `excluded_done`   | `False` | `status="Done"`     |
| Goals        | `include_complete`  | `excluded_complete` | `False` | `status="Complete"` |
| Reading List | `include_read`      | `excluded_read`   | `False` | `status="Read"`     |

The response flags allow the agent to say: "I didn't include completed tasks. Want me to search those too?"

## Agent Contract

**CRITICAL RULE**: If `fuzzy_match_quality == "weak"`:
- The agent **MUST** ask a clarification question
- The agent **MUST NOT** perform write operations (create, update, delete)

This keeps safety logic out of the API layer but ensures the agent does not silently act on uncertain matches.

## Agent Workflow

After implementation, the agent can:

1. User: "mark the email task as done"
2. Agent: `query_tasks(name_filter="email")` → returns 2-3 matches
3. Response: `{"results": [...], "fuzzy_match_quality": "good", "excluded_done": true}`
4. Agent picks best match (quality is "good")
5. Agent: `update_task(task_id="abc", status="Done")`

**Weak match scenario:**
1. User: "update the xyz task"
2. Agent: `query_tasks(name_filter="xyz")` → no good matches
3. Response: `{"results": [...], "fuzzy_match_quality": "weak", "excluded_done": true}`
4. Agent **must** ask: "I couldn't find a task matching 'xyz'. Did you mean one of these: [list]?"

## Files to Modify

- `src/api/notion/common/utils.py` - Add `filter_by_fuzzy_name` function
- `src/api/notion/tasks/models.py` - Add `name_filter`, `include_done`, update response with `excluded_done`
- `src/api/notion/tasks/endpoints.py` - Apply fuzzy filter and status exclusion
- `src/api/notion/goals/models.py` - Same changes
- `src/api/notion/goals/endpoints.py` - Same changes
- `src/api/notion/reading_list/models.py` - Same changes
- `src/api/notion/reading_list/endpoints.py` - Same changes

## Future Considerations

- **Matching improvements**: Current approach uses `partial_ratio` on the full name string. Token-based or weighted matching may be added if false positives become common.
- **Per-item scores**: If needed, would be added as a separate field (e.g., `match_score` on each result item) to avoid breaking the `fuzzy_match_quality` contract.

## Success Criteria

1. User can say "update the email task" and agent finds it
2. Query results are limited to top 5 relevant matches
3. Typos and partial names work ("emails" matches "Read emails")
4. Response includes `fuzzy_match_quality` so agent knows when to ask for clarification
5. Completed items excluded by default, with `excluded_*` flag visible to agent
6. Agent refuses to act on "weak" matches without clarification