# PRD: Telegram Integration & Session Management

## 1. Overview

### Purpose

Integrate the existing **AI Agent & Tool Registry layer** into a **Telegram chat interface**, providing conversational access with session management, safety confirmation, and persistence.

This phase explicitly supports **two transport modes**:

* **Polling mode** for local development (default)
* **Webhook mode** for production deployment

The Telegram integration is intentionally lightweight and avoids high-level Telegram frameworks. All interaction is done via **direct Telegram Bot HTTP APIs** to keep behaviour explicit and debuggable.

This phase assumes the AI Agent core already exists and focuses purely on:

* Telegram ingress
* session lifecycle
* conversational state
* user confirmation flows

---

## 2. Goals & Non-Goals

### Goals

* Provide a natural Telegram chat interface to the AI agent
* Maintain short-lived conversational sessions
* Persist messages and tool usage for audit/debugging
* Enforce human-in-the-loop confirmation for sensitive actions

### Non-Goals

* Building the agent logic itself
* Multi-user or public bot support
* Rich Telegram UI components (buttons, menus)

---

## 3. User Experience

### Core Principles

* Free-text interaction
* Minimal commands
* Explicit confirmation for risky actions
* Clear explanations of performed actions

### Commands

* `/newchat` – immediately reset the current session

---

## 4. Session Behaviour

* One Telegram chat ID is allowed
* One active session at a time
* Session expires after **10 minutes of inactivity**
* New session clears conversational context

Session expiration is transparent to the user.

---

## 5. Architecture

### Shared Core

Both polling and webhook modes delegate to the same core handler.

```
Telegram Transport (Polling or Webhook)
        ↓
Message Handler
        ↓
Session Manager (Postgres)
        ↓
AI Agent Entry Point
        ↓
Agent Response
        ↓
Telegram Send Message API
```

The transport layer is swappable via configuration.

---

## 6. Core Components

### 6.1 Telegram Transport Layer

Two supported modes:

#### Polling Mode (Local Development Default)

* Uses Telegram `getUpdates` API with **long polling**
* Typical long-poll timeout: 30–60 seconds
* No public HTTP endpoint required
* Runs as a single long-lived process
* Ideal for local development and early deployment

#### Webhook Mode (Production)

* Uses Telegram webhook delivery
* Requires public HTTPS endpoint
* Deployed behind EC2 with a public IP and domain (eg `pa.oliverking.me.uk`)
* Webhook endpoint implemented in FastAPI
* Supports horizontal scaling if required

Mode selection is controlled via configuration:

* `TELEGRAM_MODE=polling|webhook`

---

### 6.2 Telegram Webhook (Webhook Mode Only)

* FastAPI endpoint
* Secret path or header token for verification
* Immediate 200 OK response
* No business logic inside the endpoint

---

### 6.3 Polling Runner (Polling Mode Only)

* Long-running loop calling `getUpdates`
* Maintains `update_id` offset
* Delegates messages to shared handler
* Handles graceful shutdown

---

### 6.4 Message Handler (Shared)

Single source of truth for message handling.

Responsibilities:

* Enforce chat ID allowlist
* Session lookup / creation / expiry
* `/newchat` command handling
* HITL confirmation logic
* Invoke AI Agent
* Persist messages and tool events
* Return plain-text response

---

### 6.2 Session Manager

Manages session lifecycle and conversational memory.

Responsibilities:

* Create new sessions
* Expire inactive sessions
* Attach messages to sessions
* Store confirmation state

---

### 6.3 Conversation Memory

Stored in Postgres.

Data stored:

* user messages
* assistant responses
* timestamps

Only last N messages are loaded into the agent context.

---

### 6.4 Confirmation Flow (HITL)

When the agent proposes a sensitive action:

1. Bot asks for confirmation (yes/no)
2. User response is stored as confirmation state
3. Agent is re-invoked with confirmation context

No sensitive tool is executed without explicit confirmation.

---

## 7. Data Model

### Chat Session

* id (UUID)
* chat_id
* started_at
* last_activity_at
* is_active

### Chat Message

* session_id
* role (user | assistant)
* content
* created_at

### Confirmation State

* session_id
* pending_action_summary
* expires_at

### Polling Cursor (Polling Mode)

* last_update_id

---

## 8. Functional Requirements

### FR1: Webhook Handling

* Accept Telegram updates
* Ignore unauthorised chat IDs

### FR2: Session Lifecycle

* Start new session on inactivity or `/newchat`
* Persist session timestamps

### FR3: Agent Invocation

* Pass user input and recent history to agent
* Return final agent output to Telegram

### FR4: Confirmation Handling

* Intercept sensitive actions
* Request confirmation
* Resume agent only after confirmation

---

## 9. Non-Functional Requirements

* Idempotent webhook handling
* Reasonable latency (<5s typical)
* Graceful failure messages

---

## 10. Implementation Checklist (Phase 2)

### Phase 2A: Polling-Based Local Development

* [ ] Implement Telegram HTTP client (sendMessage, getUpdates)
* [ ] Polling runner with long polling (30–60s timeout)
* [ ] Update offset persistence
* [ ] Chat ID allowlist
* [ ] Shared message handler
* [ ] Session persistence and expiry
* [ ] Agent invocation wiring

### Phase 2B: Webhook-Based Production Mode

* [ ] FastAPI webhook endpoint
* [ ] Webhook secret path or header validation
* [ ] Telegram webhook registration
* [ ] Domain configuration (`pa.oliverking.me.uk`)
* [ ] Switch transport via config

### Phase 2C: Safety & Hardening

* [ ] Confirmation state handling
* [ ] Tool audit logging
* [ ] Graceful error messages
* [ ] Retry and timeout handling

---

## 11. Success Criteria

* Polling mode works fully locally with no public ingress
* Switching to webhook requires no business logic changes
* Sessions reset correctly after inactivity or `/newchat`
* No sensitive action executes without confirmation
* Telegram integration remains thin and explicit
