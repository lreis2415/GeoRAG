"""JWT verification using the Java service's RSA public key.

This module intentionally never loads or handles the Java private key. The
private key remains owned by the Java authentication service.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import jwt
from dotenv import load_dotenv

load_dotenv()


DEFAULT_PUBLIC_KEY_PATH = Path(".secrets/jwt/public.pem")


class TokenVerificationError(ValueError):
    """Raised when a JWT cannot be verified or does not meet the contract."""


class PublicKeyLoadError(RuntimeError):
    """Raised when the configured RSA public key cannot be loaded."""


def get_public_key_path() -> Path:
    """Return the configured public key path, resolved from the project root."""
    import os

    configured_path = os.getenv("JWT_PUBLIC_KEY_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_PUBLIC_KEY_PATH
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[2]
        path = project_root / path
    return path


@lru_cache(maxsize=1)
def load_public_key() -> str:
    """Load and cache the Java JWT RSA public key."""
    path = get_public_key_path()
    try:
        public_key = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PublicKeyLoadError(
            f"JWT public key cannot be read from '{path}'"
        ) from exc

    if not public_key.strip():
        raise PublicKeyLoadError(f"JWT public key is empty: '{path}'")
    return public_key


def verify_token(token: str) -> Dict[str, Any]:
    """Verify a Java-issued RS256 JWT and return its claims.

    Required claims are deliberately limited to the current Java contract:
    ``sub`` (user ID) and ``exp`` (expiration time). Issuer and audience are
    not checked because they were not included in the supplied contract.
    """
    if not isinstance(token, str) or not token.strip():
        raise TokenVerificationError("JWT token is required")

    try:
        payload = jwt.decode(
            token,
            load_public_key(),
            algorithms=["RS256"],
            options={"require": ["sub", "exp"]},
        )
    except PublicKeyLoadError:
        raise
    except jwt.InvalidTokenError as exc:
        # Do not expose token contents or cryptographic details to callers.
        raise TokenVerificationError("Invalid or expired JWT token") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise TokenVerificationError("JWT subject must be a non-empty string")

    return payload
