# Security Practices

Rules for secure coding, input validation, authentication, and secrets handling.

## Input Validation

### Validate at System Boundaries

Validate all input from external sources:

```python
from pydantic import BaseModel, Field, field_validator
import re


class CreateUserRequest(BaseModel):
    """Request to create a new user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=254)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower()
```

### Sanitise User-Provided Content

```python
import html
from markupsafe import escape


def sanitise_html(content: str) -> str:
    """Escape HTML entities to prevent XSS."""
    return html.escape(content)


def sanitise_for_display(user_input: str) -> str:
    """Sanitise user input for safe display in templates."""
    return str(escape(user_input))
```

### Path Traversal Prevention

```python
from pathlib import Path


def safe_file_path(base_dir: Path, user_filename: str) -> Path:
    """Safely resolve a user-provided filename within a base directory.

    :param base_dir: The allowed base directory.
    :param user_filename: User-provided filename.
    :returns: Safe absolute path.
    :raises ValueError: If path escapes base directory.
    """
    # Resolve to absolute path
    safe_path = (base_dir / user_filename).resolve()

    # Ensure it's still within base_dir
    if not safe_path.is_relative_to(base_dir.resolve()):
        raise ValueError(f"Path traversal detected: {user_filename}")

    return safe_path
```

### SQL Injection Prevention

Always use parameterised queries:

```python
# Bad: String formatting allows injection
query = f"SELECT * FROM users WHERE id = '{user_id}'"

# Good: Parameterised query
from sqlalchemy import text

result = session.execute(
    text("SELECT * FROM users WHERE id = :user_id"),
    {"user_id": user_id}
)

# Good: ORM handles parameterisation
user = session.query(User).filter(User.id == user_id).first()
```

### Command Injection Prevention

Never pass user input directly to shell commands:

```python
import subprocess


# Bad: Shell injection vulnerability
def bad_ping(host: str) -> str:
    return subprocess.check_output(f"ping -c 1 {host}", shell=True)


# Good: Use list form, avoid shell=True
def safe_ping(host: str) -> str:
    # Validate input first
    if not re.match(r"^[a-zA-Z0-9.-]+$", host):
        raise ValueError("Invalid hostname")

    result = subprocess.run(
        ["ping", "-c", "1", host],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout
```

## Authentication

### Token Validation

```python
import secrets
import hmac
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify bearer token using constant-time comparison.

    :param credentials: The HTTP authorization credentials.
    :returns: The verified token.
    :raises HTTPException: If token is invalid.
    """
    expected = os.environ.get("API_AUTH_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication not configured",
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    return credentials.credentials
```

### Generate Secure Tokens

```python
import secrets


def generate_api_token() -> str:
    """Generate a cryptographically secure API token."""
    return secrets.token_urlsafe(32)  # 256 bits of entropy


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return f"{secrets.randbelow(1000000):06d}"
```

## Secrets Management

### Environment Variables

```python
import os


def get_required_secret(name: str) -> str:
    """Get a required secret from environment.

    :param name: Environment variable name.
    :returns: The secret value.
    :raises ValueError: If secret is not set.
    """
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Required secret {name} is not configured")
    return value


# Usage
API_TOKEN = get_required_secret("API_AUTH_TOKEN")
DATABASE_URL = get_required_secret("DATABASE_URL")
```

### Never Log Secrets

```python
# Bad
logger.info(f"Connecting with token: {api_token}")
logger.debug(f"Database URL: {database_url}")

# Good
logger.info("Connecting to API")
logger.debug(f"Database host: {urlparse(database_url).hostname}")
```

### Redacting Secrets in Error Messages

```python
def redact_url(url: str) -> str:
    """Redact password from database URL."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    if parsed.password:
        redacted = parsed._replace(
            netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}"
        )
        return urlunparse(redacted)
    return url


# Use in error messages
logger.error(f"Database connection failed: url={redact_url(database_url)}")
```

## Rate Limiting

Protect endpoints from abuse:

```python
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import HTTPException, Request


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[datetime]] = defaultdict(list)

    def check(self, client_id: str) -> None:
        """Check if client is rate limited.

        :param client_id: Client identifier (IP, API key, etc.).
        :raises HTTPException: If rate limit exceeded.
        """
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[client_id] = [
            t for t in self.requests[client_id] if t > minute_ago
        ]

        if len(self.requests[client_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
            )

        self.requests[client_id].append(now)


rate_limiter = RateLimiter(requests_per_minute=100)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter.check(client_ip)
    return await call_next(request)
```

## CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

# Restrictive CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific origins, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

## Security Headers

```python
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)
```

## Dependency Security

- Regularly update dependencies: `poetry update`
- Check for vulnerabilities: `pip-audit` or `safety check`
- Pin dependency versions in production
- Review new dependencies before adding

## OWASP Top 10 Checklist

| Risk                      | Mitigation                                        |
|---------------------------|---------------------------------------------------|
| Injection                 | Parameterised queries, input validation           |
| Broken Auth               | Secure token handling, constant-time comparison   |
| Sensitive Data Exposure   | Encrypt at rest, HTTPS, don't log secrets         |
| XXE                       | Disable external entity processing in XML parsers |
| Broken Access Control     | Validate permissions on every request             |
| Security Misconfiguration | Secure defaults, remove debug in prod             |
| XSS                       | Escape output, Content-Security-Policy            |
| Insecure Deserialisation  | Validate and sanitise deserialised data           |
| Vulnerable Components     | Keep dependencies updated                         |
| Insufficient Logging      | Log security events, protect log files            |
