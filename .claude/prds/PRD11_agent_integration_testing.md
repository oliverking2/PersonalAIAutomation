# PRD11: Agent Integration Testing Framework

## Problem Statement

The agent module has complex multi-turn conversation flows that are difficult to test with unit tests alone. We need an integration testing framework that can simulate realistic conversation scenarios and verify correct behaviour.

## Required Test Scenarios

### 1. Clarification Flow
**Scenario**: User makes a request, agent asks for details, user provides details.

```
User: "Add a task for writing christmas cards"
Agent: "I need more details - due date and task group?"
User: "personal and due at the end of this week"
→ Agent should use create_task with correct parameters
→ Tool selector should NOT re-select tools (or should keep create_task)
```

**Assertions**:
- Agent asks for clarification (no tool use on first turn)
- After clarification, correct tool is called with correct args
- Relative date ("end of this week") is resolved correctly

### 2. Confirmation Flow
**Scenario**: User triggers a sensitive tool, confirms the action.

```
User: "Create a task to review Q4 report"
Agent: [tool_use: create_task] → confirmation required
User: "yes"
→ Task is created successfully
→ Agent confirms completion
```

**Assertions**:
- Confirmation request is returned with correct action summary
- After "yes", tool executes without re-calling LLM for tool selection
- Final response confirms the action

### 3. Confirmation with Followup
**Scenario**: User confirms AND adds a new request in the same message.

```
User: "Create a task for emails"
Agent: [confirmation required]
User: "yes, and also create one for calendar cleanup"
→ First task is created
→ Agent processes second request
```

**Assertions**:
- First tool executes
- User's full message is visible to LLM
- Second request is processed (may trigger another confirmation)

### 4. Denial Flow
**Scenario**: User denies a pending confirmation.

```
User: "Delete all my tasks"
Agent: [confirmation required]
User: "no, cancel that"
→ Action is cancelled
→ Agent acknowledges cancellation
```

**Assertions**:
- Action is NOT executed
- Response indicates cancellation
- Conversation can continue normally

### 5. Intent Change During Confirmation
**Scenario**: User changes their mind while confirmation is pending.

```
User: "Create a task for X"
Agent: [confirmation required]
User: "actually, show me my existing tasks first"
→ Pending action is cancelled
→ New request is processed with fresh tool selection
```

**Assertions**:
- Pending confirmation is cleared
- NEW_INTENT is detected
- Tools are re-selected for new request
- query_tasks is used instead of create_task

### 6. Multi-Task Creation
**Scenario**: User asks to create multiple items at once.

```
User: "Add 2 tasks: one for emails, one for subscriptions"
Agent: "I need details for each - due dates and groups?"
User: "both work and both due 1st jan"
→ Agent creates both tasks (may require 2 confirmations)
```

**Assertions**:
- Agent understands it needs to create 2 tasks
- Clarification is requested appropriately
- Both tasks are created with correct parameters
- Tool selector maintains context across turns

### 7. Tool Not Available Recovery
**Scenario**: LLM requests a tool that wasn't selected.

```
[Internal: only query_tasks selected]
LLM tries to use create_task
→ Error result is returned for unknown tool
→ LLM should recover gracefully
```

**Assertions**:
- Error result is provided for ALL tool uses in batch
- No Bedrock validation error
- LLM can respond with helpful message

### 8. Context Window Management
**Scenario**: Long conversation triggers sliding window.

```
[15+ messages in conversation]
User: "Add another task"
→ Sliding window summarises old messages
→ Context is preserved
→ New request works correctly
```

**Assertions**:
- Summarisation is triggered at threshold
- Summary captures key information
- Agent can still reference earlier context
- New requests work correctly

### 9. Error Recovery
**Scenario**: Tool execution fails.

```
User: "Create a task for X"
[API call fails]
→ Error is captured
→ Agent informs user gracefully
```

**Assertions**:
- Error is logged
- User receives helpful error message
- Conversation can continue

### 10. Relative Date Handling
**Scenario**: User uses relative dates in requests.

```
User: "Add a task due end of this week"
→ Date is calculated correctly (e.g., 2025-12-28 for Saturday)

User: "Add a task due next Friday"
→ Date is calculated correctly

User: "Add a task due tomorrow"
→ Date is calculated correctly
```

**Assertions**:
- System prompt includes today's date
- LLM correctly interprets relative dates
- Correct ISO date is passed to tool

## Testing Framework Requirements

### Mock Infrastructure
- Mock Bedrock client with configurable responses
- Mock API client for tool handlers
- Ability to inject specific LLM responses for each turn

### Conversation Simulation
- Helper to run multi-turn conversations
- Ability to assert on intermediate states
- Capture all tool calls, confirmations, and responses

### Assertions
- Tool call verification (name, args)
- Response content matching
- State verification (pending confirmations, selected tools)
- Message count and structure

### Example Test Structure

```python
class TestConversationFlows(unittest.TestCase):
    def test_clarification_flow(self):
        conv = ConversationSimulator()

        # Turn 1: Initial request
        result = conv.send("Add a task for christmas cards")
        self.assertEqual(result.tool_calls, [])
        self.assertIn("due date", result.response.lower())

        # Turn 2: Provide details
        result = conv.send("personal and end of week")
        self.assertEqual(result.stop_reason, "confirmation_required")
        self.assertEqual(result.confirmation_request.tool_name, "create_task")

        # Turn 3: Confirm
        result = conv.send("yes")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, "create_task")
        self.assertIn("christmas cards", result.response)
```

## Implementation Notes

- Consider using pytest fixtures for common setups
- May need deterministic mock responses (not real LLM)
- Could use recorded conversations for regression testing
- Integration with CI/CD for automated testing
