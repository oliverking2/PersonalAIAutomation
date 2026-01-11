"""FastAPI application configuration."""

import logging
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.health import router as health_router
from src.api.memory import router as memory_router
from src.api.models import ErrorResponse
from src.api.notion import router as notion_router
from src.api.reminders import router as reminders_router
from src.api.security import verify_token
from src.api.webhooks import router as webhooks_router
from src.observability.sentry import init_sentry
from src.utils.logging import configure_logging

configure_logging()
init_sentry()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Personal AI Automation API",
    version="1.0.0",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorised"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@app.middleware("http")
async def log_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Log incoming request ID for traceability."""
    request_id = request.headers.get("X-Request-ID", "no-request-id")
    logger.debug(f"Incoming request: {request.method} {request.url.path} request_id={request_id}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with readable messages."""
    messages: list[str] = []
    for error in exc.errors():
        loc: Any = error.get("loc", [])
        field = ".".join(str(part) for part in loc if part != "body") or "request"
        error_type = error.get("type", "")
        input_value = error.get("input")
        ctx: Any = error.get("ctx", {})

        if error_type == "enum":
            messages.append(
                f"'{field}': invalid value '{input_value}'. Expected: {ctx.get('expected', '')}"
            )
        elif error_type == "missing":
            messages.append(f"'{field}': field required")
        elif error_type == "string_too_short":
            messages.append(f"'{field}': must be at least {ctx.get('min_length', 1)} character(s)")
        elif error_type == "date_from_datetime_parsing":
            messages.append(f"'{field}': invalid date format. Expected: YYYY-MM-DD")
        else:
            messages.append(f"'{field}': {error.get('msg', 'invalid value')}")

    if len(messages) == 1:
        detail = f"Validation error: {messages[0]}"
    else:
        detail = "Validation errors: " + "; ".join(messages)

    return JSONResponse(status_code=422, content={"detail": detail})


app.include_router(health_router)
app.include_router(webhooks_router)  # Webhooks handle their own authentication
app.include_router(memory_router, dependencies=[Depends(verify_token)])
app.include_router(notion_router, dependencies=[Depends(verify_token)])
app.include_router(reminders_router, dependencies=[Depends(verify_token)])

logger.info("FastAPI application created")
