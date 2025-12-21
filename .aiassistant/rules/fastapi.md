---
apply: by model decision
instructions: When working with FastAPI, APIRouter, HTTP endpoints, or request/response models
---

## FastAPI
- Use FastAPI idioms:
  - Prefer `APIRouter` and dependency injection patterns over ad-hoc globals.
  - Use Pydantic models for request/response schemas and validation.
- Design endpoints to be explicit and stable:
  - clear routes and nouns
  - appropriate status codes
  - consistent error responses (match existing project behaviour)
- Keep request handlers thin:
  - orchestration in the route
  - business logic in dedicated services/modules
- Avoid leaking internal exception details to clients. Convert to appropriate HTTP errors following existing patterns.
- If introducing new endpoints, include tests that cover:
  - success response
  - validation error
  - at least one failure mode
