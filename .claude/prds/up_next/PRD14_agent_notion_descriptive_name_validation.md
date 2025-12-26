# PRD14: Descriptive Name Validation for Tasks and Goals

**Status: PROPOSED**

## Problem Statement

When users create tasks or goals via the agent, they often use vague or ambiguous names:
- "email task"
- "meeting"
- "thing for work"
- "fix the bug"

These names become meaningless when revisited weeks later. Users can't remember what "email task" referred to, and fuzzy search returns too many matches because the name lacks specificity.

The agent should act as a helpful assistant that prompts for better names before creating items with vague titles.

## Requirements

1. **Name validation**: Detect vague or ambiguous task/goal names before creation
2. **Clarification prompts**: Ask specific questions to improve name quality
3. **Helpful suggestions**: Provide examples of better names
4. **Override capability**: Allow users to proceed with vague names if they insist
5. **Non-blocking**: Don't reject names outright; guide users to better ones

## Vague Name Indicators

### Heuristic Rules

| Rule | Examples | Threshold |
|------|----------|-----------|
| Too short | "task", "email" | < 15 characters |
| Common vague words | "thing", "stuff", "item", "task" | Word in blocklist |
| Missing context | "meeting", "review", "fix" | Single generic verb/noun |
| Ambiguous pronouns | "this", "that", "it" | Pronoun without referent |

### Blocklist Words
```python
VAGUE_WORDS = {
    # Generic nouns
    "task", "thing", "stuff", "item", "work", "project",
    # Standalone verbs (need objects)
    "do", "fix", "check", "review", "update", "finish",
    # Pronouns without context
    "this", "that", "it", "something",
    # Vague time references
    "later", "soon", "sometime",
}
```

### Good Name Characteristics

A good name should:
1. Be specific enough to identify uniquely via fuzzy search
2. Contain actionable context (what to do, with what)
3. Be understandable without additional context weeks later
4. Be 15-60 characters (readable but descriptive)

## Implementation Approach

### Option A: Tool-Level Validation (Recommended)

Add validation in the tool handlers before calling the API:

```python
def create_task(args: TaskCreateRequest) -> dict[str, Any]:
    """Create a new task via API."""

    # Check for vague name
    validation = validate_task_name(args.task_name)
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

The agent sees `needs_clarification: True` and asks the user for more details instead of proceeding.

### Option B: System Prompt Instructions

Add explicit instructions to the agent's system prompt:

```
When creating tasks or goals, ensure names are specific and descriptive:

BEFORE CREATING, validate the name:
- If < 15 characters, ask for more detail
- If contains only generic words (task, thing, meeting), ask what specifically
- If missing context (who, what, where), ask for clarification

EXAMPLES:
- "email task" → Ask: "What specifically about email? e.g., 'Reply to Sarah's budget question'"
- "meeting prep" → Ask: "Which meeting? e.g., 'Prepare Q1 review slides for Monday standup'"
- "Review Q4 report" → Good, create directly
```

### Option C: Hybrid (Recommended for Production)

Combine both approaches:
1. System prompt gives guidance (reduces LLM hallucination of vague names)
2. Tool validation catches any that slip through
3. Tool returns structured "needs clarification" response

## Validation Logic

```python
from dataclasses import dataclass
from enum import StrEnum

class ValidationReason(StrEnum):
    TOO_SHORT = "too_short"
    VAGUE_WORDS = "vague_words"
    MISSING_CONTEXT = "missing_context"

@dataclass
class NameValidation:
    is_valid: bool
    reason: ValidationReason | None = None
    suggestion: str | None = None

VAGUE_WORDS = {"task", "thing", "stuff", "item", "meeting", "email", "work", "fix", "check"}
MIN_NAME_LENGTH = 15

def validate_task_name(name: str) -> NameValidation:
    """Validate task name is descriptive enough.

    :param name: The proposed task name.
    :returns: Validation result with reason and suggestion if invalid.
    """
    name_lower = name.lower().strip()
    words = set(name_lower.split())

    # Check length
    if len(name) < MIN_NAME_LENGTH:
        return NameValidation(
            is_valid=False,
            reason=ValidationReason.TOO_SHORT,
            suggestion=f"'{name}' is quite short. Can you add more detail? "
                       f"e.g., what specifically, for whom, or by when?",
        )

    # Check for predominantly vague words
    non_vague_words = words - VAGUE_WORDS
    if len(non_vague_words) < 2:
        return NameValidation(
            is_valid=False,
            reason=ValidationReason.VAGUE_WORDS,
            suggestion=f"'{name}' is a bit vague. What specifically needs to be done? "
                       f"Adding context helps you find this task later.",
        )

    return NameValidation(is_valid=True)
```

## Agent Workflow

### Vague Name Flow
```
User: "Create a task to fix the bug"

Tool: validate_task_name("fix the bug")
      → is_valid=False, reason=TOO_SHORT

Tool returns: {
    "needs_clarification": True,
    "reason": "too_short",
    "suggestion": "'fix the bug' is quite short. Can you add more detail?"
}

Agent: "I'd like to create a more specific task so you can find it later.
Which bug are you referring to? For example:
- 'Fix login timeout bug in auth module'
- 'Fix CSS alignment bug on dashboard'"

User: "It's the null pointer exception in the payment service"

Agent: Creates task "Fix null pointer exception in payment service"
```

### Good Name Flow
```
User: "Create a task to review Sarah's Q4 budget proposal"

Tool: validate_task_name("review Sarah's Q4 budget proposal")
      → is_valid=True

Agent: Creates task directly, no clarification needed
```

### User Override Flow
```
User: "Just create a task called 'meeting'"

Agent: "That name is quite vague - you might not remember which meeting
later. Would you like to add more detail, or should I create it as-is?"

User: "Create it as-is, I'll remember"

Agent: Creates task "meeting" (respects user preference)
```

## Tool Description Updates

```python
ToolDef(
    name="create_task",
    description=(
        "Create a new task. Requires a DESCRIPTIVE task name (15+ chars), "
        "task group, and due date. "
        "If the name is vague (e.g., 'email task', 'meeting'), the tool will "
        "return needs_clarification=True. In that case, ask the user for more "
        "specific details before retrying. "
        "Good names: 'Review Sarah's Q4 proposal', 'Fix auth timeout bug'. "
        "Bad names: 'task', 'email', 'meeting prep'."
    ),
    # ...
)
```

## Files to Modify

### New Files
- `src/agent/validation.py` - Name validation logic and NameValidation dataclass

### Modified Files
- `src/agent/tools/tasks.py` - Add validation before create, handle needs_clarification
- `src/agent/tools/goals.py` - Same pattern
- `src/agent/tools/reading_list.py` - Same pattern (for title validation)

## Configuration

```python
# src/agent/validation.py

# Minimum characters for a "good" name
MIN_NAME_LENGTH = 15

# Words that alone don't make a specific name
VAGUE_WORDS = {
    "task", "thing", "stuff", "item", "work", "project",
    "meeting", "email", "call", "review", "fix", "check",
    "update", "do", "finish", "complete", "prep", "prepare",
}

# How many non-vague words required
MIN_SPECIFIC_WORDS = 2
```

## Testing

### Test Cases

```python
class TestNameValidation(unittest.TestCase):
    def test_valid_name(self):
        result = validate_task_name("Review Sarah's Q4 budget proposal")
        self.assertTrue(result.is_valid)

    def test_too_short(self):
        result = validate_task_name("fix bug")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, ValidationReason.TOO_SHORT)

    def test_vague_words(self):
        result = validate_task_name("prepare for meeting tomorrow")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, ValidationReason.VAGUE_WORDS)

    def test_borderline_length(self):
        # 15 chars exactly
        result = validate_task_name("Fix auth bug #1")
        self.assertTrue(result.is_valid)

    def test_specific_despite_short(self):
        # Contains specific context even if somewhat short
        result = validate_task_name("PR #123 review")
        # This should pass because it has specific identifiers
```

## Success Criteria

1. Agent prompts for clarification on vague names 90%+ of the time
2. Users can still create vague names if they insist (no hard blocking)
3. Task/goal names created via agent are findable via fuzzy search
4. No noticeable latency added to create flow
5. Clarification prompts are helpful, not annoying

## Metrics to Track

- Percentage of create requests that trigger clarification
- Average name length before vs after implementation
- User override rate (how often they proceed with vague names anyway)
- Fuzzy search success rate for agent-created items

## Future Considerations

- **Learning from user patterns**: If user always provides good names, skip validation
- **Domain-specific rules**: Different validation for work vs personal tasks
- **Auto-enhancement**: Suggest improved names rather than just asking for more detail
- **Integration with PRD13**: If page content is required, name validation could be lighter
