"""FastAPI dependencies for authenticated requests."""

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


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> CurrentUser:
    """Require and verify a Bearer JWT for a protected FastAPI endpoint."""
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
