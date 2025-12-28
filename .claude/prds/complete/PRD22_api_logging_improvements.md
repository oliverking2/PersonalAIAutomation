# PRD22: API Logging Improvements

**Status: IMPLEMENTED**

**Roadmap Reference**: Misc Improvements - "Add better logging to the Notion API"

## Overview

Improve logging across the `src/api/` module to enable effective debugging and monitoring of API operations.

## Problem Statement

Current API logging is minimal and makes diagnosing issues difficult:

```python
# Current pattern (e.g., tasks/endpoints.py)
@router.get("")
async def query_tasks(...):
    logger.debug("Querying tasks")  # No filter info, no result count
    results = client.query_all_pages(...)
    return [...]  # Silent on how many items returned
```

**Current Gaps**:

1. **No parameter visibility**: Can't see what filters, sorts, or search terms were used
2. **No response counts**: Queries don't log how many items were found/returned
3. **No timing information**: Can't identify slow operations
4. **No flow tracking**: Multi-step operations (get + parse + fetch content) have no intermediate logs
5. **No HTTP status codes on success**: Only failures are logged
6. **Minimal error context**: Exception logs lack details about what was being attempted
7. **No bulk operation summaries**: Batch creates don't log X succeeded, Y failed

**Impact**: When issues occur, diagnosing requires adding temporary debug logging, redeploying, and reproducing the issue.

## Proposed Solution

### 1. Request Context Logging

Log incoming request parameters at INFO level:

```python
# src/api/notion/tasks/endpoints.py

@router.get("")
async def query_tasks(
    name_filter: str | None = None,
    status_filter: TaskStatus | None = None,
    ...
):
    logger.info(
        f"Query tasks: name_filter={name_filter!r}, "
        f"status_filter={status_filter}, limit={limit}"
    )
    results = client.query_all_pages(...)
    logger.info(f"Query tasks complete: found={len(results)}")
    return [...]
```

### 2. Response Summary Logging

Log result counts and key metadata:

```python
# After query operations
logger.info(f"Query tasks complete: found={len(results)}")

# After get operations
logger.info(f"Retrieved task: id={task_id}, name={task.name!r}")

# After create operations
logger.info(f"Created task: id={page_id}, name={args.name!r}")

# After update operations
logger.info(f"Updated task: id={task_id}, fields={list(args.model_dump(exclude_unset=True).keys())}")
```

### 3. Operation Timing

Add timing for operations that may be slow:

```python
import time

@router.get("/{task_id}")
async def get_task(task_id: str, ...):
    start = time.perf_counter()
    logger.info(f"Retrieving task: id={task_id}")

    page = client.get_page(task_id)
    task = parse_page_to_task(page)
    content = await _fetch_page_content(client, task_id)

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Retrieved task: id={task_id}, name={task.name!r}, "
        f"elapsed={elapsed_ms:.0f}ms"
    )
    return TaskResponse(...)
```

### 4. Bulk Operation Summaries

Log progress and summary for batch operations:

```python
@router.post("/bulk")
async def create_tasks(args: BulkCreateTasksArgs, ...):
    logger.info(f"Bulk create tasks: count={len(args.tasks)}")

    results = {"created": [], "failed": []}
    for i, task_args in enumerate(args.tasks):
        try:
            page_id = client.create_page(...)
            results["created"].append(page_id)
            logger.debug(f"Bulk create [{i+1}/{len(args.tasks)}]: created {page_id}")
        except NotionClientError as e:
            results["failed"].append({"name": task_args.name, "error": str(e)})
            logger.warning(f"Bulk create [{i+1}/{len(args.tasks)}]: failed {task_args.name!r}: {e}")

    logger.info(
        f"Bulk create tasks complete: "
        f"succeeded={len(results['created'])}, failed={len(results['failed'])}"
    )
    return results
```

### 5. Error Context Enhancement

Include operation context in exception logs:

```python
# Current (insufficient context)
except NotionClientError as e:
    logger.exception(f"Failed to create task: {e}")

# Proposed (actionable context)
except NotionClientError as e:
    logger.exception(
        f"Failed to create task: name={args.name!r}, "
        f"status={args.status}, priority={args.priority}, error={e}"
    )
```

### 6. Dependency Initialisation

Log when dependencies are created:

```python
# src/api/notion/dependencies.py

def get_notion_client() -> NotionClient:
    logger.debug("Initialising Notion client")
    try:
        client = NotionClient()
        logger.debug("Notion client initialised successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialise Notion client: {e}")
        raise
```

## Implementation Details

### Logging Levels

| Level | Use Case |
|-------|----------|
| DEBUG | Intermediate steps, dependency init, pagination cursors |
| INFO | Request start/end, response counts, timing, operation summaries |
| WARNING | Partial failures in bulk ops, validation failures, retries |
| ERROR | Unrecoverable failures, configuration errors |

### Standard Log Format

Adopt consistent key=value format for machine parsing:

```python
# Good: Consistent, parseable
logger.info(f"Query tasks: name_filter={name_filter!r}, status={status}, found={len(results)}")

# Bad: Inconsistent, hard to parse
logger.info(f"Querying tasks with filter '{name_filter}' returned {len(results)} results")
```

### Files to Update

| File | Changes |
|------|---------|
| `src/api/notion/tasks/endpoints.py` | Request params, response counts, timing |
| `src/api/notion/goals/endpoints.py` | Request params, response counts, timing |
| `src/api/notion/reading_list/endpoints.py` | Request params, response counts, timing |
| `src/api/notion/ideas/endpoints.py` | Request params, response counts, timing |
| `src/api/notion/common/pages/endpoints.py` | Operation details, error context |
| `src/api/notion/common/databases/endpoints.py` | Operation details |
| `src/api/notion/common/datasources/endpoints.py` | Query params, result counts |
| `src/api/notion/dependencies.py` | Client initialisation |
| `src/api/health/endpoints.py` | Health check details |

## Implementation Steps

1. Define logging conventions in `CLAUDE.md` (log format, levels)
2. Update `src/api/notion/tasks/endpoints.py` as reference implementation
3. Apply pattern to remaining Notion endpoints (goals, reading_list, ideas)
4. Update common endpoints (pages, databases, datasources)
5. Add timing wrapper utility if timing pattern is repetitive
6. Update dependencies.py with initialisation logging
7. Update tests to not be affected by new logging (if needed)

## Testing

No new tests required - logging changes are additive and don't affect behaviour. Existing tests should pass unchanged.

Manual verification:
1. Enable DEBUG level logging
2. Make API requests and verify logs contain expected context
3. Verify timing appears for slow operations
4. Verify bulk operations show progress and summary

## Alternatives Considered

### Structured Logging Library (structlog)

- Pros: Machine-parseable JSON output, automatic context binding
- Cons: New dependency, learning curve, overkill for current scale
- Decision: Use standard logging with consistent key=value format

### Request/Response Middleware

- Pros: Automatic logging of all requests
- Cons: Less control over what's logged, can't include domain-specific context
- Decision: Endpoint-level logging provides better context

### OpenTelemetry Tracing

- Pros: Distributed tracing, spans for timing
- Cons: Significant complexity, infrastructure requirements
- Decision: Defer until needed for production observability

## Success Criteria

1. All API endpoints log request parameters at INFO level
2. All query endpoints log result counts
3. Get/Create/Update operations log identifiers and key fields
4. Bulk operations log summary (succeeded/failed counts)
5. Error logs include operation context (what was being attempted)
6. Logs use consistent key=value format
7. No performance regression from logging overhead
