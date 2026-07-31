"""FastAPI dependencies for authenticated requests."""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .jwt import PublicKeyLoadError, TokenVerificationError, verify_token


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated identity derived only from JWT claims."""

    user_id: str
    username: Optional[str]
    role: Optional[str]
    claims: Dict[str, Any]


http_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authentication_enabled() -> bool:
    """Read the auth switch on every request so local debugging is easy."""
    value = os.getenv("AUTH_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _debug_user() -> CurrentUser:
    """Return a deterministic local identity when authentication is disabled."""
    user_id = os.getenv("AUTH_DEBUG_USER_ID", "debug-user").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "AUTH_DEBUG_USER_ID must be configured when authentication "
                "is disabled"
            ),
        )
    return CurrentUser(
        user_id=user_id,
        username="debug-user",
        role="DEBUG",
        claims={"sub": user_id, "debug": True},
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> CurrentUser:
    """Resolve the current user from JWT, or a local debug identity."""
    if not _authentication_enabled():
        return _debug_user()

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = verify_token(credentials.credentials)
    except PublicKeyLoadError as exc:
        # This is a server configuration problem, not a client auth failure.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT public key is not configured correctly",
        ) from exc
    except TokenVerificationError as exc:
        raise _unauthorized("Invalid or expired JWT token") from exc

    return CurrentUser(
        user_id=payload["sub"],
        username=payload.get("name"),
        role=payload.get("userType"),
        claims=payload,
    )
