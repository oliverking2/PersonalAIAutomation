# PRD: AI Agent & Tool Registry Layer (Bedrock Converse)

## 1. Overview

### Purpose

Design and implement a **standalone AI Agent layer** that uses **AWS Bedrock Converse with tool use** to safely and deterministically execute internal tools.

This phase deliberately excludes any chat platform integration (eg Telegram). The agent is designed as a reusable core that can later be embedded into multiple clients.

Primary goals:

* Structured tool calling via LLMs
* Strong guardrails and validation
* Scalability from a handful of tools to ~50 tools
* Clear separation between reasoning and business logic

---

## 2. Goals & Non-Goals

### Goals

* Provide a reusable agent runtime built on Bedrock Converse
* Allow LLM-driven multi-step workflows (query → update → confirm)
* Centralise tool definitions and schemas
* Prevent tool misuse or hallucinated identifiers

### Non-Goals

* Conversational UI
* Session persistence or chat history
* Multi-user routing
* Managed Bedrock Agents
* Framework-driven orchestration (LangChain, CrewAI)

---

## 3. Core Design Principles

* **Explicit contracts**: all tools have strict schemas
* **Small context**: only expose relevant tools per request
* **Fail safely**: ambiguity leads to clarification, not action
* **Deterministic execution**: bounded loops and sequential tool calls
* **Model-agnostic core**: Bedrock-specific logic isolated at edges

---

## 4. Architecture

```
Client (any)
   ↓
Agent Entry Point
   ↓
Tool Selector (AI-first)
   ↓
Agent Runner (Bedrock Converse)
   ↓
Tool Registry → Tool Handlers
   ↓
Internal APIs (Notion, etc)
```

---

## 5. Components

### 5.1 Tool Registry

Central in-process registry that defines all available tools.

Each tool definition includes:

* name (unique)
* description (LLM-facing)
* tags (eg `reading`, `tasks`)
* risk level (`safe` | `sensitive`)
* Pydantic args model
* Python handler

Responsibilities:

* Validate uniqueness at registration
* Provide filtered tool subsets
* Generate JSON schemas from Pydantic models

---

### 5.2 Tool Selector

AI-first selector that determines which **subset of tools** should be exposed for a given user request.

Inputs:

* user intent text
* metadata summary of all tools

Outputs:

* ordered list of tool names (≤ configurable limit)

Rules:

* Prefer safe tools
* Include sensitive tools only when state change is clearly implied
* Fallback to tag-based heuristics if AI selection fails

---

### 5.3 Agent Runner

The Agent Runner executes the reasoning and tool-calling loop.

Responsibilities:

* Construct system prompt
* Attach selected tool schemas
* Execute tool calls sequentially
* Feed tool results back to the model
* Enforce max-step limits

Constraints:

* Max tool calls per run: default 5
* One tool per step
* No parallel execution

---

### 5.4 Tool Handlers

Thin wrappers around internal APIs.

Rules:

* No business logic
* Single responsibility
* Structured JSON return
* These will be python functions. In some cases, it will be a wrapper around the FastAPI endpoints.

---

## 6. Safety & Risk Handling

### Risk Classification

* **Safe tools**: read-only or additive actions
* **Sensitive tools**: destructive or irreversible actions

Sensitive tools must never be executed implicitly.

### Human-in-the-Loop (HITL)

For sensitive tools:

1. Agent produces an **action summary**
2. Client must explicitly confirm before re-invoking agent with confirmation context
3. Only then is the sensitive tool exposed

The agent layer supports confirmation but does not own UI concerns.

---

## 7. Functional Requirements

### FR1: Tool Registration

* Tools can be registered at startup
* Duplicate names are rejected
* Tool schemas derived automatically from Pydantic

### FR2: Tool Selection

* ≤ N tools selected per request
* Selection explainable via metadata

### FR3: Tool Execution

* Strict input validation
* Graceful handling of tool failures
* Structured error propagation

### FR4: Agent Loop

* Multi-step reasoning supported
* Loop terminates on final response or max steps

---

## 8. Non-Functional Requirements

* Deterministic behaviour
* Bounded execution time
* Observable tool usage
* Minimal prompt size

---

## 9. Implementation Checklist (Phase 1)

* [x] ToolDef and ToolRegistry
* [x] Tool registration for reading list domain
* [x] ToolSelector (AI-first)
* [x] AgentRunner with Bedrock Converse
* [x] Tool schema generation
* [x] Max-step enforcement
* [x] HITL confirmation contract

---

## 10. Success Criteria

* Agent selects correct tools consistently
* Adding tools does not require prompt rewrites
* Sensitive tools cannot be executed accidentally
* Core agent reusable across clients
