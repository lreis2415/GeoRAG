"""Unit tests for Java-issued JWT verification."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.jwt import (
    PublicKeyLoadError,
    TokenVerificationError,
    load_public_key,
    verify_token,
)
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture
def rsa_keys(tmp_path, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_path = tmp_path / "public.pem"
    key_path.write_bytes(public_pem)
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(key_path))
    load_public_key.cache_clear()
    yield private_key
    load_public_key.cache_clear()


def make_token(private_key, **claims):
    now = datetime.now(timezone.utc)
    payload = {"sub": "user-1001", "exp": now + timedelta(minutes=5), **claims}
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_verify_valid_java_token(rsa_keys):
    token = make_token(rsa_keys, name="Alice", userType="USER")

    payload = verify_token(token)

    assert payload["sub"] == "user-1001"
    assert payload["name"] == "Alice"
    assert payload["userType"] == "USER"


def test_verify_requires_sub_and_exp(rsa_keys):
    now = datetime.now(timezone.utc)
    token_without_sub = jwt.encode(
        {"exp": now + timedelta(minutes=5)}, rsa_keys, algorithm="RS256"
    )
    token_without_exp = jwt.encode(
        {"sub": "user-1001"}, rsa_keys, algorithm="RS256"
    )

    with pytest.raises(TokenVerificationError):
        verify_token(token_without_sub)
    with pytest.raises(TokenVerificationError):
        verify_token(token_without_exp)


def test_verify_rejects_expired_token(rsa_keys):
    token = make_token(
        rsa_keys,
        exp=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    with pytest.raises(TokenVerificationError):
        verify_token(token)


def test_verify_rejects_wrong_key(rsa_keys):
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(other_private_key)

    with pytest.raises(TokenVerificationError):
        verify_token(token)


def test_fastapi_dependency_returns_current_user(rsa_keys, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    token = make_token(rsa_keys, name="Alice", userType="ADMIN")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    current_user = get_current_user(credentials)

    assert isinstance(current_user, CurrentUser)
    assert current_user.user_id == "user-1001"
    assert current_user.username == "Alice"
    assert current_user.role == "ADMIN"


def test_missing_credentials_returns_401(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("AUTH_ENABLED", "true")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None)

    assert exc_info.value.status_code == 401


def test_auth_can_be_disabled_for_local_debugging(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("AUTH_DEBUG_USER_ID", "local-debug-user")

    current_user = get_current_user(None)

    assert current_user.user_id == "local-debug-user"
    assert current_user.role == "DEBUG"


def test_disabled_auth_requires_debug_user_id(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("AUTH_DEBUG_USER_ID", "")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None)

    assert exc_info.value.status_code == 500


def test_missing_public_key_is_server_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(tmp_path / "missing.pem"))
    load_public_key.cache_clear()

    with pytest.raises(PublicKeyLoadError):
        verify_token("not-a-token")

    load_public_key.cache_clear()
