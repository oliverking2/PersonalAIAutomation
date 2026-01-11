# PRD29: Agent Memory System

**Status: UP NEXT**

**Roadmap Reference**: New feature

**Related**: PRD082 (Context Management), PRD09 (Conversation Tracking)

## Overview

Implement persistent memory across chat sessions, allowing the agent to recall important facts, preferences, and context from previous conversations. Memory is stored in PostgreSQL and loaded into the conversation context at the start of each session.

## Problem Statement

Currently, each conversation starts fresh. The agent has no recall of:
- Factual information mentioned in past sessions (e.g., "Alec is my boss")
- User preferences expressed over time
- Recurring context that shouldn't need repeating

**Issues:**
1. Users repeat themselves across sessions
2. The agent can't build up knowledge about the user's world
3. No continuity between unrelated conversations
4. Important context gets lost when conversations summarise or end

## Proposed Solution

A simple, explicit memory system with three components:

1. **Memory table** in PostgreSQL to store memory entries
2. **Memory tools** (`add_to_memory`, `update_memory`) for the agent to manage memories
3. **Memory loading** into the prompt context at conversation start (part of cached prefix)
4. **`/memory` command** for users to view and manage stored memories

### Design Principles

- **Proactive with confirmation**: Agent notices facts worth remembering and asks before storing
- **Update over contradict**: When information changes, update the existing memory rather than adding conflicting entries
- **Simple first**: Start with a flat memory store, evolve to retrieval if needed
- **Cacheable**: Memory is static during a conversation, so it can be cached
- **User-visible**: Users can see and manage what the agent remembers via `/memory`

## Data Model

The data model uses two tables: `AgentMemory` (the logical entity) and `AgentMemoryVersion` (content history). This cleanly separates "what we're remembering" from "how it's evolved over time".

### Short IDs

To save tokens in the prompt context, memories use short 8-character IDs instead of full UUIDs:

```python
import secrets
import string

# A-Za-z0-9 = 62 chars, 8 chars = 62^8 ≈ 218 trillion combinations
ALPHABET = string.ascii_letters + string.digits  # A-Za-z0-9

def generate_short_id() -> str:
    """Generate an 8-character alphanumeric ID."""
    return "".join(secrets.choice(ALPHABET) for _ in range(8))
```

```python
class AgentMemory(Base):
    """A logical memory entity - the 'thing' being remembered."""

    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)

    # What this memory is about
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    versions: Mapped[list["AgentMemoryVersion"]] = relationship(
        back_populates="memory",
        order_by="AgentMemoryVersion.version_number",
    )

    __table_args__ = (
        Index("idx_agent_memories_category", "category"),
        Index("idx_agent_memories_subject", "subject"),
        Index("idx_agent_memories_deleted_at", "deleted_at"),
    )

    @property
    def is_active(self) -> bool:
        """Check if this memory is active (not deleted)."""
        return self.deleted_at is None

    @property
    def current_content(self) -> str | None:
        """Get the latest version's content."""
        if self.versions:
            return self.versions[-1].content
        return None

    @property
    def current_version(self) -> "AgentMemoryVersion | None":
        """Get the latest version."""
        if self.versions:
            return self.versions[-1]
        return None


class AgentMemoryVersion(Base):
    """A version of a memory's content - tracks history over time."""

    __tablename__ = "agent_memory_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Link to parent memory (uses short ID)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("agent_memories.id"), nullable=False
    )

    # Version tracking
    version_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Source tracking
    source_conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_conversations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # Relationships
    memory: Mapped["AgentMemory"] = relationship(back_populates="versions")

    __table_args__ = (
        Index("idx_memory_versions_memory_id", "memory_id"),
        Index("idx_memory_versions_created_at", "created_at"),
    )
```

### Memory History Pattern

When `update_memory` is called:
1. Find the memory by ID
2. Create a new `AgentMemoryVersion` with `version_number = current + 1`
3. Return confirmation with the memory ID (unchanged)

This preserves full history with simple queries:

```sql
-- View full history for a memory
SELECT v.version_number, v.content, v.created_at
FROM agent_memory_versions v
WHERE v.memory_id = 'abc-123'
ORDER BY v.version_number;

-- Result shows evolution:
-- v1: "Sarah works on Platform team"   (2024-01-01)
-- v2: "Sarah works on Design team"     (2024-01-15)
-- v3: "Sarah is Design team lead"      (2024-02-01)
```

Loading active memories with their latest content:

```python
def load_active_memories(session: Session) -> list[AgentMemory]:
    """Load all active memories with their versions eagerly loaded.

    IMPORTANT: Order by category then created_at to ensure consistent
    ordering for prompt caching. If order changes, cache is invalidated.
    """
    return (
        session.query(AgentMemory)
        .options(selectinload(AgentMemory.versions))
        .filter(AgentMemory.deleted_at.is_(None))
        .order_by(AgentMemory.category, AgentMemory.created_at)
        .all()
    )
```

### Memory Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `person` | Information about people | "Alec is my boss at TechCorp" |
| `preference` | User preferences | "I prefer tasks due on Friday" |
| `context` | Recurring context | "I work on the Platform team" |
| `project` | Project-specific info | "Project X uses Python 3.12" |

```python
class MemoryCategory(StrEnum):
    PERSON = "person"
    PREFERENCE = "preference"
    CONTEXT = "context"
    PROJECT = "project"
```

## API Endpoints

Memory is managed via API endpoints, with tools calling the API for validation and separation of concerns.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/memory/` | List all active memories |
| `GET` | `/api/memory/{id}` | Get a memory with version history |
| `POST` | `/api/memory/` | Create a new memory |
| `PUT` | `/api/memory/{id}` | Update a memory (creates new version) |
| `DELETE` | `/api/memory/{id}` | Soft-delete a memory |

### Request/Response Models

```python
class CreateMemoryRequest(BaseModel):
    content: str = Field(..., min_length=5, max_length=500)
    category: MemoryCategory
    subject: str | None = Field(None, max_length=200)


class UpdateMemoryRequest(BaseModel):
    content: str = Field(..., min_length=5, max_length=500)


class MemoryResponse(BaseModel):
    id: str  # Short 8-char ID
    category: MemoryCategory
    subject: str | None
    content: str  # Current version content
    version: int
    created_at: datetime
    updated_at: datetime | None  # Latest version timestamp


class MemoryListResponse(BaseModel):
    memories: list[MemoryResponse]
    total: int
```

## Agent Tool Design

Memory tools are **always available** - they bypass normal tool selection since memory management is a core agent capability, not domain-specific.

### add_to_memory Tool

```python
class AddToMemoryArgs(BaseModel):
    """Arguments for adding to memory."""

    content: str = Field(
        ...,
        description="The fact or information to remember",
        min_length=5,
        max_length=500,
    )
    category: MemoryCategory = Field(
        ...,
        description="Category of memory: person, preference, context, or project"
    )
    subject: str | None = Field(
        None,
        description="Optional subject/entity this memory relates to (e.g., person name, project name)",
        max_length=200,
    )


ADD_TO_MEMORY_TOOL = ToolDef(
    name="add_to_memory",
    description=(
        "Store important information for future conversations. Use this when the user "
        "shares facts about people, expresses preferences, or provides context that would "
        "be useful to remember. Ask for confirmation before storing new information."
    ),
    input_schema={...},
    handler=add_to_memory_handler,  # Calls POST /api/memory/
    risk_level=RiskLevel.LOW,
    requires_confirmation=False,  # Confirmation is conversational, not HITL
    tags=frozenset({"system", "memory"}),  # System tools always available
)
```

### update_memory Tool

```python
class UpdateMemoryArgs(BaseModel):
    """Arguments for updating an existing memory."""

    memory_id: str = Field(
        ...,
        description="8-character ID of the memory to update"
    )
    content: str = Field(
        ...,
        description="The updated content for this memory",
        min_length=5,
        max_length=500,
    )


UPDATE_MEMORY_TOOL = ToolDef(
    name="update_memory",
    description=(
        "Update an existing memory when information has changed. Use this instead of "
        "creating a new memory when correcting outdated information."
    ),
    input_schema={...},
    handler=update_memory_handler,  # Calls PUT /api/memory/{id}
    risk_level=RiskLevel.LOW,
    requires_confirmation=False,  # No confirmation needed for updates
    tags=frozenset({"system", "memory"}),
)
```

### System Tools

Memory tools are marked with `tags={"system"}` which means:
1. They bypass the normal tool selection process
2. They're always included in the agent's available tools
3. They don't count towards the domain tool limit

### Tool Behaviour

**add_to_memory:**
1. Validate the input
2. Call `POST /api/memory/` with content, category, subject
3. API checks for existing memory with same subject
4. If similar exists, return suggestion to use `update_memory` instead
5. Otherwise create memory and return confirmation with ID

**update_memory:**
1. Validate the memory ID
2. Call `PUT /api/memory/{id}` with new content
3. API creates new version, returns old → new content
4. No confirmation needed - just update it

The memory ID stays the same across updates - only the version changes.

### When to Store Memories

Memory management should be mostly invisible - the agent handles it in the background. The key is knowing when to ask for confirmation vs when to just do it.

#### Ask for confirmation (new information):

When storing **new** information, briefly confirm:

```
User: "Alec is my boss by the way"
Agent: "Got it - should I remember that for future conversations?"
User: "Yes"
Agent: [Uses add_to_memory]
```

Keep it lightweight - a quick confirmation, not a formal request. The goal is to avoid storing things the user mentioned casually that they don't want remembered.

#### Just do it (updates to existing memories):

When **updating** existing information, no need to ask:

```
User: "Actually Sarah moved to the Design team"
Agent: [Uses update_memory]
       "Updated - I now have Sarah on the Design team."
```

#### High-confidence auto-store:

For very explicit statements, can store without asking:

```
User: "Remember that I prefer Friday due dates"
Agent: [Uses add_to_memory]
       "Noted - I'll remember your preference for Friday due dates."
```

```
User: "From now on, always set reminders for 9am"
Agent: [Uses add_to_memory]
       "Got it - 9am reminders going forward."
```

#### When to store:

- Facts about people (names, roles, relationships)
- Explicit preferences ("I prefer...", "always...", "from now on...")
- Recurring context ("I work at...", "My project uses...")
- Corrections to existing memories

#### When NOT to store:

- Transient information ("I'm tired today")
- Task-specific details ("This task is for the Monday meeting")
- Information already in memory
- Casual mentions that aren't meant to be permanent

#### Err on the side of asking

When uncertain, ask. It's better to briefly confirm than to fill memory with noise. Over time, the agent will learn what's worth remembering.

### Updating vs Adding

When information changes, the agent should update rather than add:

```
[Memory exists: "Sarah works on the Platform team"]

User: "Sarah moved to the Design team last week"
Agent: "I'll update my memory - Sarah is now on the Design team instead of Platform."
Agent: [Uses update_memory tool]
```

The agent can identify memories to update by:
1. Checking the subject field (e.g., subject="Sarah")
2. Looking at the memory context included in the system prompt
3. Using the memory ID shown in the `/memory list` output

## Memory Loading

### At Conversation Start

Memory is loaded once at conversation start and included in the cached prompt prefix.

```python
def build_memory_context(memories: list[AgentMemory]) -> str:
    """Build memory context for the system prompt.

    :param memories: Active memory entries.
    :returns: Formatted memory section.
    """
    if not memories:
        return ""

    grouped = defaultdict(list)
    for mem in memories:
        grouped[mem.category].append(mem)

    lines = ["## Your Memory", ""]
    lines.append("The following is information you've learned about the user from previous conversations.")
    lines.append("Use this context naturally. To update a memory, use the update_memory tool with the memory ID.")
    lines.append("")

    for category, entries in grouped.items():
        lines.append(f"### {category.title()}")
        for entry in entries:
            # Include short ID for reference in updates
            short_id = str(entry.id)[:8]
            subject_prefix = f"[{entry.subject}] " if entry.subject else ""
            lines.append(f"- [id:{short_id}] {subject_prefix}{entry.content}")
        lines.append("")

    return "\n".join(lines)
```

### Memory in System Prompt

Memory is appended to the system prompt after the static instructions. Memory IDs are included so the agent can reference them when updating:

```
[Static system prompt - instructions, capabilities, etc.]

## Your Memory

The following is information you've learned about the user from previous conversations.
Use this context naturally. To update a memory, use the update_memory tool with the memory ID.

### Person
- [id:a1b2c3d4] [Alec] Alec is the user's boss at TechCorp
- [id:e5f6g7h8] [Sarah] Sarah is a colleague on the Design team

### Preference
- [id:i9j0k1l2] User prefers tasks to have due dates on Fridays
- [id:m3n4o5p6] User likes concise responses

### Context
- [id:q7r8s9t0] User works on the Platform team
- [id:u1v2w3x4] User's timezone is Europe/London
```

### Caching Strategy

Memory is part of the cacheable prefix because:
1. It doesn't change during a conversation
2. It's loaded once at conversation start
3. It should be consistent throughout the session

**Critical: Consistent ordering for cache effectiveness**

Memories must be loaded in a deterministic order. If the order changes between requests, the cache is invalidated. We order by:
1. Category (alphabetically)
2. Created timestamp (ascending within category)

This ensures the same memory set always produces the same prompt text.

The memory block sits between the system prompt and the conversation summary:

```
[System prompt] <- Cached
[Memory context] <- Cached (deterministic ordering)
---
[Conversation summary] <- Not cached (changes frequently)
[Recent messages] <- Not cached
```

Note: The conversation summary is **not** cached as it changes frequently during multi-turn conversations. Only the system prompt and memory context are stable enough to benefit from caching.

## Implementation Phases

### Phase 1: Data Model & Operations

1. Create `src/database/memory/` module
   - `models.py`: `AgentMemory` and `AgentMemoryVersion` models
   - `operations.py`: CRUD operations for both tables
   - `__init__.py`: Exports
2. Create migration for both tables
3. Add `MemoryCategory` enum to `src/agent/enums.py`
4. Add `generate_short_id()` utility
5. Unit tests for operations

### Phase 2: API Endpoints

1. Create `src/api/memory/` module
   - `models.py`: Request/response Pydantic models
   - `endpoints.py`: CRUD endpoints
   - `__init__.py`: Router exports
2. Mount router in `src/api/app.py`
3. Unit tests for endpoints

### Phase 3: Memory Tools

1. Create `src/agent/tools/memory.py`
   - Tool definitions that call API endpoints
   - Mark as system tools (always available)
2. Update `ToolRegistry` to support system tools that bypass selection
3. Unit tests for tool handlers

### Phase 4: Memory Loading

1. Add `build_memory_context()` to `src/agent/utils/memory.py`
2. Update `AgentRunner` to load and inject memory at conversation start
3. Update system prompt template to include memory section
4. Integration tests for memory loading

### Phase 5: /memory Command & Agent Behaviour

1. Add `/memory` command to Telegram handler (direct API calls, no agent):
   - `/memory` or `/memory list` - calls `GET /api/memory/`
   - `/memory delete <id>` - calls `DELETE /api/memory/{id}`
2. Update system prompt to instruct agent on memory usage
3. Add guidance for when to ask vs auto-store
4. Test end-to-end memory creation, update, and recall

## Files to Create

| File | Purpose |
|------|---------|
| `src/database/memory/__init__.py` | Module exports |
| `src/database/memory/models.py` | `AgentMemory` and `AgentMemoryVersion` models |
| `src/database/memory/operations.py` | CRUD operations for both tables |
| `src/api/memory/__init__.py` | API module exports |
| `src/api/memory/endpoints.py` | REST endpoints for memory CRUD |
| `src/api/memory/models.py` | Request/response Pydantic models |
| `src/agent/tools/memory.py` | Memory tool definitions (call API) |
| `src/agent/utils/memory.py` | Memory context building utilities |
| `testing/database/memory/test_operations.py` | Operation tests |
| `testing/api/memory/test_endpoints.py` | API endpoint tests |
| `testing/agent/tools/test_memory.py` | Tool handler tests |
| `testing/agent/utils/test_memory.py` | Memory utilities tests |

## Files to Modify

| File | Changes |
|------|---------|
| `src/agent/enums.py` | Add `MemoryCategory` enum |
| `src/agent/runner.py` | Load memory at conversation start |
| `src/agent/utils/templates.py` | Add memory section to system prompt |
| `src/agent/utils/tools/registry.py` | Register memory tools as system tools |
| `src/api/app.py` | Mount memory router |
| `src/messaging/telegram/handler.py` | Add `/memory` command (direct API call) |
| `alembic/versions/` | New migration for `agent_memories` and `agent_memory_versions` tables |

## Success Criteria

1. Agent can store facts shared by user across conversations
2. Agent can update existing memories when information changes
3. Memory persists in PostgreSQL and survives restarts
4. Memory loads at conversation start and is available throughout
5. Memory is included in cached prompt prefix (efficient)
6. Agent proactively suggests storing with user confirmation
7. `/memory` command allows viewing and deleting memories
8. No regression in existing conversation functionality
9. All tests pass with 80%+ coverage

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Memory grows unbounded | `/memory delete` command; future: TTL or relevance pruning |
| Wrong info stored | Agent asks for confirmation before storing |
| Memory bloats context | Start with simple list; future: RAG retrieval for large memory |
| Stale/outdated memory | `update_memory` tool for corrections; `updated_at` tracking |
| Privacy concerns | Single-user system; future: encryption at rest |

## Future Enhancements

### v2: Memory Retrieval (RAG)

For larger memory stores, switch from loading all memories to semantic retrieval:

```python
def retrieve_relevant_memories(
    query: str,
    memories: list[AgentMemory],
    top_k: int = 10,
) -> list[AgentMemory]:
    """Retrieve memories relevant to the current query."""
    # Embed query
    # Compare to pre-computed memory embeddings
    # Return top_k most similar
```

### v2: Memory Importance

Add importance scoring for prioritisation when context is limited:

```python
importance: Mapped[float]  # 0.0-1.0, decay over time if not accessed
last_accessed_at: Mapped[datetime | None]
access_count: Mapped[int]
```

## Testing Scenarios

### Scenario 1: Proactive Memory Suggestion

```
User: "Alec is my boss by the way"
Agent: "Would you like me to remember that Alec is your boss for future conversations?"
User: "Yes"
Agent: [Uses add_to_memory tool]
        - content: "Alec is the user's boss"
        - category: person
        - subject: "Alec"
Agent: "Done - I'll remember that Alec is your boss."
```

### Scenario 2: Memory Recall in New Session

```
[New conversation - memory loaded with: "[id:a1b2c3d4] [Alec] Alec is the user's boss"]
User: "Can you create a task to update Alec on the project?"
Agent: [Knows from memory that Alec is the boss]
       "I'll create a task to update Alec on the project."
```

### Scenario 3: Memory Update (Information Changed)

```
[Memory exists: "[id:e5f6g7h8] [Sarah] Sarah works on the Platform team"]
User: "Sarah moved to the Design team last week"
Agent: [Uses update_memory tool]
        - memory_id: e5f6g7h8
        - content: "Sarah works on the Design team"
       "Updated - I now have Sarah on the Design team."
```

### Scenario 4: User Declines Memory Storage

```
User: "I'm working with James on this project"
Agent: "Would you like me to remember that James is a project collaborator?"
User: "No, it's just for this task"
Agent: "No problem, I won't store that."
[No tool called]
```

### Scenario 5: /memory Command (Direct, No Agent)

The `/memory` command queries the API directly without creating an agent conversation:

```
User: /memory
[Telegram handler calls GET /api/memory/ directly]

Bot response:
"📝 Your memories:

**Person**
• [a1b2c3d4] Alec is the user's boss
• [e5f6g7h8] Sarah works on the Design team

**Preference**
• [i9j0k1l2] User prefers Thursday due dates

Use /memory delete <id> to remove a memory."
```

### Scenario 6: Memory Deletion (Direct, No Agent)

```
User: /memory delete i9j0k1l2
[Telegram handler calls DELETE /api/memory/i9j0k1l2 directly]

Bot response:
"Deleted: 'User prefers Thursday due dates'"
```

## Notes

- This is a single-user system, so no multi-tenancy concerns
- Memory is user-specific by default (could add user_id later)
- Start simple, iterate based on actual usage patterns
- Agent should not be overly eager - only suggest storing genuinely useful information
