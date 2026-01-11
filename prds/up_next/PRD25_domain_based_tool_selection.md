2# PRD25: Domain-Based Tool Selection

**Status: UP NEXT**

**Roadmap Reference**: AGENT-004 (High Priority)

**Related**: PRD10 (Internal Tool Selection), PRD19 (CRUD Tool Factory)

## Overview

Update the ToolSelector to use domain-based grouping instead of individual tool selection. When a domain is identified (e.g., "tasks"), include ALL tools for that domain rather than just the specific operation mentioned.

## Problem Statement

In long conversations, users often need multiple operations within the same domain:

```
User: "Create a task called buy groceries"
→ Selector picks: create_tasks

User: "Actually, delete that task"
→ Selector tries to add delete_task but may fail due to context issues
```

**Issues**:
1. Specific tool selection doesn't account for natural conversation flow
2. Users expect to perform any operation on a domain once they start working with it
3. Additive mode helps but relies on LLM correctly identifying new tools needed
4. Missing tools cause conversation failures and user frustration

## Proposed Solution

Switch from individual tool selection to domain-based grouping:

```
User: "Create a task called buy groceries"
→ Selector identifies domain: tasks
→ Returns ALL task tools: query_tasks, get_task, create_tasks, update_task
```

### Key Changes

1. **Add `domain:X` tags** to tools (e.g., `domain:tasks`, `domain:goals`)
2. **Update ToolSelector** to identify domains and expand to all domain tools
3. **Set max 10 tools** per conversation with domain-aware prioritisation
4. **Update factory** to auto-inject domain tags

## Design

### Domain Tags

Add explicit domain tag prefix to distinguish from operation tags:

```python
# Current tags
tags=frozenset({"tasks", "query", "list"})

# New tags with domain prefix
tags=frozenset({"domain:tasks", "query", "list"})
```

### CRUDToolConfig Changes

Factory auto-injects domain tag:

```python
@dataclass(frozen=True)
class CRUDToolConfig:
    domain: str
    domain_plural: str
    # ... existing fields ...

    @property
    def domain_tag(self) -> str:
        """Get the domain tag for this config."""
        return f"domain:{self.domain_plural}"
```

### ToolRegistry Changes

Add domain-aware methods:

```python
class ToolRegistry:
    def get_domains(self) -> set[str]:
        """Get all unique domain tags."""

    def get_tools_by_domain(self, domain_tag: str) -> list[ToolDef]:
        """Get all tools for a specific domain."""

    def get_domain_tool_count(self) -> dict[str, int]:
        """Get count of tools per domain."""
```

### ToolSelector Changes

New domain-based selection algorithm:

```python
class ToolSelector:
    def __init__(
        self,
        registry: ToolRegistry,
        max_tools: int = 10,      # Increased from 5
        max_domains: int = 3,     # New: limit domain count
    ) -> None:
        ...

    def select(
        self,
        user_intent: str,
        current_tools: list[str] | None = None,
    ) -> ToolSelectionResult:
        """Select tools using domain-based grouping."""
        # 1. Identify relevant domains from intent
        # 2. Expand domains to all their tools
        # 3. Respect max_tools limit with prioritisation
```

### Selection Flow

```
User Intent + Domain History
    │
    ▼
┌─────────────────────┐
│ Domain Selection    │  "Create a task" → ["domain:tasks"]
│ (LLM identifies     │
│  relevant domains)  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Domain Expansion    │  ["domain:tasks"] → [query_tasks, get_task,
│ (Get ALL tools      │                       create_tasks, update_task]
│  for each domain)   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Recency-Based       │  If >max_tools:
│ Pruning             │  - Drop oldest/least relevant domains entirely
│                     │  - Never partial domains, always complete
└─────────────────────┘
```

### Domain Recency and Pruning

Domains are tracked with recency - most recently referenced domains are kept when the limit is exceeded.

**Key principles:**
1. **Complete domains only**: Never include partial domains. Either all tools for a domain or none.
2. **Recency wins**: Most recently used domains stay, oldest get dropped
3. **Current intent priority**: The domain(s) mentioned in the current message always take precedence

**Example conversation flow:**

```
Turn 1: "Create a task"
  → domains: [tasks]
  → tools: 4

Turn 5: "Add a reminder for tomorrow"
  → domains: [tasks, reminders]  (tasks still recent enough)
  → tools: 8

Turn 10: "What are my goals?"
  → domains: [reminders, goals]  (tasks dropped - oldest, goals is current)
  → tools: 8

Turn 15: "Add an item to my reading list and create an idea"
  → domains: [reading, ideas]  (reminders + goals dropped, current intent prioritised)
  → tools: 8
```

**Recency tracking:**
- Maintain ordered list of domains by last-used turn
- Current message domains always moved to front
- When expanding exceeds max_tools, drop from end (oldest) until under limit

Example with max_tools=10:
- Current domains by recency: [goals (turn 8), tasks (turn 3), reading (turn 1)]
- User asks about "reminders" (turn 10)
- New domain order: [reminders, goals, tasks, reading]
- reminders (4) + goals (4) = 8 (under limit)
- tasks (4) would make 12 (over limit)
- Drop tasks and reading entirely
- Final: [reminders, goals] = 8 tools

### ToolSelectionResult Changes

Add domains field for transparency:

```python
class ToolSelectionResult(BaseModel):
    tool_names: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)  # NEW
    reasoning: str = Field(default="")
```

## Implementation

### Phase 1: Data Model Changes

1. Add `domain_tag` property to `CRUDToolConfig`
2. Update factory to auto-inject `domain:X` tag
3. Add `domains` field to `ToolSelectionResult`

### Phase 2: ToolRegistry Updates

1. Add `get_domains()` method
2. Add `get_tools_by_domain()` method
3. Add `get_domain_tool_count()` method

### Phase 3: ToolSelector Refactor

1. Add domain selection prompts
2. Add `max_domains` parameter (default: 3)
3. Update `select()` for domain-based selection
4. Add `_select_domains()` helper
5. Add `_expand_domains_to_tools()` helper
6. Update fallback selection for domain matching
7. Update additive mode to track domains

### Phase 4: Tool Definition Updates

1. Update `reminders.py` manual tools with `domain:reminders` tag
2. Verify factory-generated tools have correct domain tags
3. Remove redundant domain name from custom `tags` field (now auto-generated)

### Phase 5: Testing

1. Unit tests for ToolRegistry domain methods
2. Unit tests for ToolSelector domain selection
3. Integration tests for multi-turn conversations
4. Test prioritisation when limit exceeded

## Files to Modify

| File | Changes |
|------|---------|
| `src/agent/models.py` | Add `domains` field to `ToolSelectionResult` |
| `src/agent/tools/factory.py` | Add `domain_tag` property, auto-inject in tool creation |
| `src/agent/utils/tools/registry.py` | Add domain-aware methods |
| `src/agent/utils/tools/selector.py` | Refactor for domain-based selection |
| `src/agent/tools/reminders.py` | Add `domain:reminders` tags to manual tools |
| `testing/agent/utils/tools/test_registry.py` | Add domain method tests |
| `testing/agent/utils/tools/test_selector.py` | Add domain selection tests |

## Success Criteria

1. User can perform any operation within a domain once it's selected
2. "Create task" followed by "delete it" works without tool missing errors
3. Max 10 tools per conversation enforced with sensible prioritisation
4. Domain selection uses efficient Haiku model
5. Additive mode preserves existing domains
6. All existing tests pass (with updates)

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| More tools = higher token cost | Domain selection is still cheap (Haiku); execution only sees relevant domains |
| Wrong domain selected | LLM prompt includes domain descriptions; fallback uses keyword matching |
| Too many domains selected | Hard limit of 3 domains per selection |
| Breaking change to selection API | Keep `tool_names` in result; `domains` is additive |

## Testing Scenarios

### Scenario 1: Single Domain Conversation

```
User: "Create a task called buy groceries"
Expected: domain:tasks selected, all 4 task tools available

User: "Mark it as done"
Expected: Same tools still available, update_task used
```

### Scenario 2: Multi-Domain Conversation

```
User: "Create a task for my fitness goal"
Expected: domain:tasks + domain:goals selected (8 tools)

User: "Add a reminder for tomorrow"
Expected: domain:reminders added
  - If 12 tools > max, drop oldest domain (tasks)
  - Result: domain:goals + domain:reminders (8 tools)
```

### Scenario 3: Domain Switch with Recency

```
Turn 1: "What are my reading list items?"
Expected: domain:reading selected (4 tools)

Turn 5: "Now show me my tasks"
Expected: domain:reading + domain:tasks (8 tools)

Turn 10: "Create a reminder and add a new idea"
Expected: reading dropped (oldest), tasks dropped (2nd oldest)
  - domain:reminders + domain:ideas (8 tools)
  - User's current intent (reminders + ideas) takes priority
```

### Scenario 4: Domain Dropped Then Re-Added

```
Turn 1: "Create a task"
Expected: domain:tasks (4 tools)

Turn 5: "What are my goals and reminders?"
Expected: domain:goals + domain:reminders (8 tools)
  - tasks dropped due to max_tools

Turn 10: "Actually, update that task from earlier"
Expected: domain:tasks + domain:reminders (or goals)
  - tasks re-added as it's now current intent
  - One of goals/reminders dropped (whichever is oldest)
```
