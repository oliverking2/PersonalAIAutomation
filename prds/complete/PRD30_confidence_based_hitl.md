# PRD30: Confidence-Based HITL with Visual Diffs

**Status: UP NEXT**

**Created: 2026-01-11**

**Related**: PRD27 (Natural HITL Confirmation Messages)

---

## 1. Overview

Improve the Human-in-the-Loop (HITL) confirmation flow by:
1. **Always showing diffs** - Display before/after for content changes so users see exactly what's changing
2. **Confidence-based execution** - Skip confirmation when user explicitly requested the change; only confirm when agent is inferring or suggesting

This addresses the clunky UX where users have to ask "what are you updating it to?" and the friction of unnecessary confirmations for explicitly requested actions.

---

## 2. Problem Statement

### Problem 1: Confirmations Don't Show What's Changing

Current confirmation messages for content updates don't show the actual change:

```
I'll update the description for "Test Task" - sound good?
```

The user has no idea what the new description will be. They have to ask "what are you updating it to?" which breaks conversational flow.

This is especially problematic for batch operations where multiple descriptions are being updated.

### Problem 2: Unnecessary Confirmations for Explicit Requests

When a user explicitly says "tidy up the description of Test Task", they've already expressed intent. The agent may need to ask clarifying questions, but should not ask for confirmation once it knows what to do:

**Current (bad) - asks for confirmation:**
```
User: tidy up the description of Test Task
Agent: I'll update the description for "Test Task" - sound good?
User: yes
Agent: Done!
```

**Desired (good) - asks for clarification if needed, then executes:**
```
User: tidy up the description of Test Task
Agent: [fetches content] I see redundant phrasing and an informal test note.
       Should I clean up both, or just one?
User: both
Agent: Done! [shows diff of what changed]
```

The key difference:
- **Clarification**: "What do you want?" → User specifies → Execute immediately
- **Confirmation**: "I'm going to do X" → User approves → Execute

The user's original intent ("tidy up") should carry through any clarification exchange, so the final action executes without additional confirmation.

### Problem 3: Batch Updates Are Tedious

For operations like "tidy up descriptions for all my test tasks", the current flow would require:
1. Individual confirmation for each task, OR
2. A batch confirmation that still doesn't show what's changing

Neither provides a good UX.

---

## 3. Goals

1. **Visual clarity**: Users always see what's changing (before/after diff)
2. **Reduced friction**: Explicit requests execute immediately with a report of changes
3. **Appropriate caution**: Inferred or proactive changes still require confirmation
4. **Batch efficiency**: Multiple changes shown in a clear summary format

## 4. Non-Goals

- Undo capability (showing diff is sufficient for user to request reversal)
- Changing risk levels of existing tools
- Modifying which tools are SAFE vs SENSITIVE

---

## 5. Proposed Solution

### 5.1 Confidence Classification

Add a lightweight LLM classification step (Haiku) at tool execution time to determine whether the user explicitly requested this action. The classifier receives the full conversation context, so it can understand multi-turn exchanges.

| Classification | Definition | Example |
|----------------|------------|---------|
| `EXPLICIT` | User directly requested this specific action | "update the description to X", "tidy up the description", user said "both" after agent asked which issues to fix |
| `NEEDS_CONFIRMATION` | Agent is inferring, interpreting vaguely, or suggesting unprompted | User said "clean up my tasks" (vague), agent noticed a typo and offers to fix it |

**Key simplification**: No intent tracking across turns. The classifier sees the full conversation at classification time and can determine if the current action was explicitly requested, even through multi-turn exchanges.

### 5.2 Behaviour by Confidence Level

| Confidence | Behaviour |
|------------|-----------|
| `EXPLICIT` | Execute immediately, show diff after |
| `NEEDS_CONFIRMATION` | Show diff, ask for confirmation |

### 5.3 Message Formatting (Template-Based, Not LLM)

All user-facing messages are **template-based** (no LLM generation). The only LLM call is for confidence classification.

**Scalar fields (status, due_date, priority):** Use existing PRD27 templates - no diff needed:
```
Done! I've updated the due date for "Test Task" to 15th Jan 2025.
Done! I've marked "Code Review" as Completed.
```

**Content fields (description, notes):** Show before/after diff:
```
Done! I've tidied up "Test Task":

Before:
• "This is a test task with a description to verify task creation functionality."
• "test add description"

After:
• "This is a test task to verify task creation functionality."
```

**Batch operations (content):**
```
Done! Updated 3 task descriptions:

Test Task:
  Before: "This is a test task with a description to verify task creation functionality."
  After: "This is a test task to verify task creation functionality."

Code Review:
  Before: "Review the PR for bug fix"
  After: "Review PR #142 for null pointer fix"

Planning Doc:
  No changes needed (already clean)
```

**For confirmation requests (INFERRED/PROACTIVE content changes):**
```
I'd tidy up "Test Task" like this:

Before:
• "This is a test task with a description to verify task creation functionality."
• "test add description"

After:
• "This is a test task to verify task creation functionality."

This look right?
```

---

## 6. Technical Design

### 6.1 New Confidence Classifier

Create `src/agent/utils/confidence_classifier.py`:

```python
from enum import StrEnum
from pydantic import BaseModel
from mypy_boto3_bedrock_runtime import BedrockRuntimeClient


class ConfidenceLevel(StrEnum):
    """Classification of user intent for a proposed action."""
    EXPLICIT = "explicit"              # User directly requested this action
    NEEDS_CONFIRMATION = "needs_confirmation"  # Agent inferring or suggesting


class ConfidenceClassification(BaseModel):
    """Result of confidence classification."""
    level: ConfidenceLevel
    reasoning: str


def extract_conversation_for_classification(
    messages: list[dict],
) -> list[dict]:
    """Extract only user messages and agent text responses for classification.

    Filters out tool calls, tool results, and system content to keep
    the classification context minimal and focused on user intent.

    :param messages: Full conversation messages.
    :returns: Filtered messages with only user/assistant text.
    """


def classify_action_confidence(
    client: BedrockRuntimeClient,
    messages: list[dict],
    proposed_action: str,
) -> ConfidenceClassification:
    """Classify whether the user explicitly requested this action.

    Uses Haiku for fast, cheap classification. Extracts only user messages
    and agent text responses (no tool calls/results) to keep context minimal.

    :param client: Bedrock client.
    :param messages: Full conversation messages (will be filtered).
    :param proposed_action: Human-readable description of the action.
    :returns: Classification result.
    """
    filtered = extract_conversation_for_classification(messages)
    # ... classification logic
```

**Context filtering:**
- Include: User messages, agent text responses
- Exclude: Tool use blocks, tool results, system prompts
- Result: Compact conversational context focused on user intent

**Classification prompt:**
```
You are classifying user intent for a proposed action based on a conversation.

<conversation>
{formatted_conversation}
</conversation>

Proposed action: "{proposed_action}"

Classify as:
- EXPLICIT: User directly and clearly requested this specific action. This includes:
  - Direct requests: "update X to Y", "tidy up X", "fix the typo in X"
  - Confirming a choice: Agent asked "which issues?" and user said "both"
  - Clear follow-ups to their own request
- NEEDS_CONFIRMATION: Agent is inferring, interpreting vaguely, or suggesting unprompted:
  - Vague requests: User said "clean up my tasks" without specifying what
  - Proactive suggestions: Agent noticed something and is offering to fix it

Respond with JSON: {"level": "explicit|needs_confirmation", "reasoning": "brief explanation"}
```

### 6.2 Diff Formatting

Extend `src/agent/utils/formatting.py` with diff display:

```python
def format_content_diff(
    entity_name: str,
    old_content: str | None,
    new_content: str,
) -> str:
    """Format a before/after diff for content changes.

    :param entity_name: Name of the item being changed.
    :param old_content: Previous content (None if new item).
    :param new_content: New content being set.
    :returns: Formatted diff string.
    """


def format_batch_diff(
    changes: list[ContentChange],
) -> str:
    """Format multiple content changes as a summary.

    :param changes: List of changes with entity name, old/new content.
    :returns: Formatted batch diff string.
    """


@dataclass
class ContentChange:
    """A single content change for diff display."""
    entity_name: str
    old_content: str | None
    new_content: str
    changed: bool = True  # False if no actual change
```

### 6.3 Modified Runner Flow

Update `src/agent/runner.py` to use confidence-based execution:

```python
def _process_sensitive_tools(
    self,
    sensitive_contexts: list[_ToolUseContext],
    state: _RunState,
) -> AgentRunResult | None:
    """Process sensitive tools with confidence-based execution.

    :returns: AgentRunResult if confirmation needed, None to proceed.
    """
    # For each sensitive tool, classify confidence using full conversation
    for ctx in sensitive_contexts:
        classification = classify_action_confidence(
            client=self.client,
            conversation_messages=state.messages,
            proposed_action=format_action(ctx.tool_name, ctx.args),
        )

        if classification.level == ConfidenceLevel.EXPLICIT:
            # Execute immediately, will show diff in response
            ctx.confidence = ConfidenceLevel.EXPLICIT
        else:
            # Requires confirmation with diff
            return self._request_confirmation_with_diff(ctx, classification)

    return None  # All tools can proceed
```

### 6.4 Fetching Old Content for Diffs

For content changes, the agent needs the old value to show a diff. This requires:

1. **For update operations**: Fetch current content before executing (PRD28 already requires this)
2. **Store old content**: Keep the fetched content available for diff display

Add to `PendingToolAction`:

```python
class PendingToolAction(BaseModel):
    """A single tool action pending confirmation."""
    # ... existing fields ...
    old_content: str | None = None  # For diff display
    new_content: str | None = None  # For diff display
```

---

## 7. Files to Modify

### New Files

| File | Purpose |
|------|---------|
| `src/agent/utils/confidence_classifier.py` | Confidence classification logic |
| `testing/agent/utils/test_confidence_classifier.py` | Tests for classifier |

### Modified Files

| File | Changes |
|------|---------|
| `src/agent/utils/formatting.py` | Add `format_content_diff()`, `format_batch_diff()` |
| `src/agent/models.py` | Add `old_content`/`new_content` to `PendingToolAction` |
| `src/agent/runner.py` | Integrate confidence classification at tool execution time |
| `src/agent/enums.py` | Add `ConfidenceLevel` enum |
| `testing/agent/utils/test_formatting.py` | Tests for diff formatting |
| `testing/agent/test_runner.py` | Tests for confidence-based execution |

---

## 8. Implementation Steps

1. **Add ConfidenceLevel enum** to `src/agent/enums.py`
2. **Create confidence classifier** in `src/agent/utils/confidence_classifier.py`
3. **Add diff formatting functions** to `src/agent/utils/formatting.py`
4. **Extend PendingToolAction** with content fields for diffs
5. **Modify runner** to:
   - Classify confidence at tool execution time with full conversation context
   - Execute immediately for EXPLICIT, request confirmation for NEEDS_CONFIRMATION
6. **Update confirmation messages** to include diffs
7. **Update post-execution messages** to show what changed (for EXPLICIT)
8. **Add tests** for all new functionality

---

## 9. Testing

### Confidence Classifier Tests

1. **Explicit requests classified correctly**: "tidy up X", "update X to Y", "fix the typo"
2. **Multi-turn explicit classified correctly**: User said "tidy up X", agent asked "which issues?", user said "both"
3. **Needs confirmation for vague requests**: "clean up my tasks" without specifying what
4. **Needs confirmation for proactive suggestions**: Agent-initiated suggestions
5. **Edge cases**: Ambiguous requests, multi-part requests

### Diff Formatting Tests

1. **Single item diff**: Before/after displayed correctly
2. **Batch diff**: Multiple items summarised clearly
3. **No change case**: "No changes needed" displayed
4. **New content**: Handles None old_content gracefully

### Integration Tests

1. **Explicit request executes immediately**: No confirmation, diff shown after
2. **Multi-turn explicit executes**: After clarifying exchange, executes without confirmation
3. **Vague request shows confirmation**: Diff displayed, awaits approval
4. **Proactive suggestion asks permission**: Clear ask with diff
5. **Batch explicit executes all**: Summary of all changes shown

---

## 10. Success Criteria

1. Users always see what's changing (before/after) for content updates
2. Explicit requests ("tidy up X") execute without confirmation
3. Multi-turn explicit exchanges execute without confirmation (classifier sees full context)
4. Executed changes show a clear diff of what changed
5. Vague/proactive changes show diff in confirmation request
6. Batch operations display all changes in a readable summary
7. Haiku classification adds minimal latency (<500ms typical)
8. No regression in existing HITL flows for non-content changes
9. `make check` passes

---

## 11. Example Flows

### Flow 1: Explicit Request - Simple

```
User: tidy up the description of Test Task
      [Classifier sees this message, classifies as EXPLICIT]

Agent: Done! I've tidied up "Test Task":

Before:
• "This is a test task with a description to verify task creation functionality."
• "test add description"

After:
• "This is a test task to verify task creation functionality."

Removed redundant phrasing and informal test note.
```

### Flow 2: Explicit Request - With Clarification

```
User: tidy up the description of Test Task

Agent: I see two things I could tidy up:
       1. Redundant phrasing ("with a description")
       2. Informal test note ("test add description")

       Should I clean up both, or just one?

User: both
      [Classifier sees full conversation: user asked to tidy up,
       agent offered options, user chose "both" → EXPLICIT]

Agent: Done! I've tidied up "Test Task":

Before:
• "This is a test task with a description to verify task creation functionality."
• "test add description"

After:
• "This is a test task to verify task creation functionality."
```

### Flow 3: Vague Request (Confirmation with Diff)

```
User: clean up my tasks
      [Classifier sees vague request with no specific target → NEEDS_CONFIRMATION]

Agent: I'd tidy up these task descriptions:

Test Task:
  Before: "This is a test task with a description to verify task creation functionality."
  After: "This is a test task to verify task creation functionality."

Code Review:
  Before: "Review the PR for bug fix"
  After: "Review PR #142 for null pointer fix"

This look right?

User: yes

Agent: Done! Both descriptions updated.
```

### Flow 4: Proactive Suggestion (Permission Request)

```
User: show me the Test Task

Agent: Here's "Test Task":
...

I noticed the description has some redundant text. Want me to tidy it up?

Before: "This is a test task with a description..."
After: "This is a test task to verify..."
      [Classifier sees user didn't ask for changes → NEEDS_CONFIRMATION]

User: sure

Agent: Done!
```

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Haiku misclassifies intent | Conservative default to NEEDS_CONFIRMATION; monitor and tune prompt |
| Latency from classification call | Haiku is fast (~200ms); run in parallel with other processing where possible |
| Old content not available for diff | Require fetch-before-update (PRD28); gracefully handle missing old content |
| Long conversations increase classification cost | Filter to user messages and agent text only (no tool calls/results); truncate to recent turns if needed |

---

## 13. Future Considerations

- User preference for confirmation level ("always confirm", "never confirm", "smart")
- Learning from user corrections to improve classification
- Inline diff formatting (strikethrough old, highlight new) for Telegram
