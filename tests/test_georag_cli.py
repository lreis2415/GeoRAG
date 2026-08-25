"""Unit tests for the agent-facing GeoRAG CLI primitives."""

import json
import time

import httpx
import pytest

from georag_cli import __main__ as cli
from georag_cli.core import (
    ApiClient,
    AuthenticationError,
    ConnectivityError,
    CredentialStore,
    Profile,
    RequestLogger,
    require_active_token,
    token_metadata,
)


def _token(expiry: int) -> str:
    payload = json.dumps({"sub": "experiment-user", "exp": expiry}).encode()
    encoded = __import__("base64").urlsafe_b64encode(payload).decode().rstrip("=")
    return f"header.{encoded}.signature"


def test_credential_store_uses_keyring(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        "georag_cli.core.keyring.get_password",
        lambda service, user: saved.get((service, user)),
    )
    monkeypatch.setattr(
        "georag_cli.core.keyring.set_password",
        lambda service, user, value: saved.__setitem__((service, user), value),
    )
    monkeypatch.setattr(
        "georag_cli.core.keyring.delete_password",
        lambda service, user: saved.pop((service, user)),
    )

    store = CredentialStore()
    store.save_token("local", "token-value")

    assert store.get_token("local") == "token-value"
    store.delete_token("local")
    assert store.get_token("local") is None


def test_active_token_rejects_expired_token(monkeypatch):
    token = _token(int(time.time()) - 1)
    monkeypatch.setattr(CredentialStore, "get_token", lambda *_: token)

    with pytest.raises(AuthenticationError, match="expired"):
        require_active_token(CredentialStore(), "local")


def test_token_metadata_reads_subject_and_expiry():
    expiry = int(time.time()) + 60

    assert token_metadata(_token(expiry)) == {"sub": "experiment-user", "exp": expiry}


def test_api_client_sends_bearer_and_unwraps_standard_response():
    def handler(request):
        assert request.headers["authorization"] == "Bearer access-token"
        assert str(request.url) == "http://georag.test/llm/v1/models"
        return httpx.Response(
            200,
            json={
                "success": True,
                "code": 2000,
                "message": "ok",
                "data": {"chat_models": []},
            },
        )

    with ApiClient(
        Profile("http://mm.test/mbms", "http://georag.test/llm/v1"),
        token="access-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.request_json("GET", "/models")

    assert response["data"] == {"chat_models": []}


def test_api_client_maps_401_to_authentication_error():
    with ApiClient(
        Profile(),
        token="access-token",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(401, json={"detail": "invalid"})
        ),
    ) as client:
        with pytest.raises(AuthenticationError):
            client.request_json("GET", "/models")


def test_api_client_writes_structured_log_and_redacts_secrets(tmp_path):
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "success": True,
                "code": 2000,
                "message": "ok",
                "data": {"token": "server-secret"},
            },
        )

    logger = RequestLogger(tmp_path, command="auth.login")
    with ApiClient(
        Profile(),
        token="access-token",
        logger=logger,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.request_json(
            "POST",
            "/v1/auth/login",
            json_body={"userAccount": "experiment", "password": "123456"},
        )

    records = [json.loads(line) for line in logger.path.read_text().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["path"] == "/v1/auth/login"
    assert record["request"]["json"]["password"] == "[REDACTED]"
    assert record["response"]["data"]["token"] == "[REDACTED]"
    serialized = json.dumps(record)
    assert "123456" not in serialized
    assert "server-secret" not in serialized
    assert "access-token" not in serialized


def test_api_client_logs_timeout(tmp_path):
    def handler(request):
        raise httpx.ReadTimeout("upstream took too long", request=request)

    logger = RequestLogger(tmp_path, command="kb.ask")
    with ApiClient(
        Profile(),
        token="access-token",
        logger=logger,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ConnectivityError, match="timed out"):
            client.request_json(
                "POST",
                "/knowledge/ask",
                json_body={"db_name": "demo", "query": "question"},
            )

    record = json.loads(logger.path.read_text().splitlines()[0])
    assert record["path"] == "/knowledge/ask"
    assert record["status_code"] is None
    assert record["error"]["type"] == "timeout"


def test_chat_ask_omits_optional_knowledge_base(monkeypatch, capsys):
    captured = {}

    class FakeClient:
        def request_json(self, method, path, **kwargs):
            captured.update(method=method, path=path, **kwargs)
            return {"success": True, "code": 2000, "message": "ok", "data": {}}

    def fake_run_authenticated(args, callback, logger=None):
        cli._success(args, callback(FakeClient()))

    monkeypatch.setattr(cli, "_run_authenticated", fake_run_authenticated)

    assert (
        cli.main(
            [
                "--output",
                "json",
                "chat",
                "ask",
                "--query",
                "请识别问题类型",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert captured["method"] == "POST"
    assert captured["path"] == "/chat"
    assert captured["json_body"] == {
        "prompt": cli.DEFAULT_PROMPT,
        "query": "请识别问题类型",
    }


def test_auth_login_stores_token_without_printing_it(monkeypatch, capsys):
    token = _token(int(time.time()) + 3600)
    saved = {}

    class FakeStore:
        def get_token(self, _profile):
            return None

        def save_token(self, profile, value):
            saved[profile] = value

        def delete_token(self, _profile):
            return None

    class FakeConfigStore:
        def get_profile(self, _profile):
            return Profile()

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def request_json(self, *_args, **_kwargs):
            return {
                "success": True,
                "message": "succ",
                "data": {"token": token, "userId": "experiment-user"},
            }

    monkeypatch.setattr(cli, "CredentialStore", FakeStore)
    monkeypatch.setattr(cli, "ConfigStore", FakeConfigStore)
    monkeypatch.setattr(cli, "ApiClient", FakeClient)
    monkeypatch.setattr("builtins.input", lambda _: "experiment")
    monkeypatch.setattr("getpass.getpass", lambda _: "123456")

    assert cli.main(["--output", "json", "auth", "login"]) == 0
    output = capsys.readouterr().out

    assert saved == {"local": token}
    assert token not in output
    assert '"ok": true' in output
