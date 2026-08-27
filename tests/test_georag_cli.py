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

    logger = RequestLogger(tmp_path, command="chat.ask")
    with ApiClient(
        Profile(),
        token="access-token",
        logger=logger,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ConnectivityError, match="timed out"):
            client.request_json(
                "POST", "/chat", json_body={"db_name": "demo", "query": "question"}
            )

    record = json.loads(logger.path.read_text().splitlines()[0])
    assert record["path"] == "/chat"
    assert record["status_code"] is None
    assert record["error"]["type"] == "timeout"


def test_kb_ask_command_is_removed():
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["kb", "ask", "demo", "--query", "question"])


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


def _sse_body(*events) -> bytes:
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event, ensure_ascii=False)}")
        lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_stream_request_decodes_sse_events_and_ignores_frames():
    payload = b": keepalive\n" b"event: message\n" + _sse_body(
        {"type": "text", "content": "你好"},
        {"type": "sources", "sources": [{"chunk_id": "c1"}]},
        {"type": "done", "response": "你好", "session_id": "s-1"},
    )

    def handler(request):
        assert request.headers["authorization"] == "Bearer access-token"
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=payload
        )

    with ApiClient(
        Profile("http://mm.test/mbms", "http://georag.test/llm/v1"),
        token="access-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        events = list(
            client.stream_request("POST", "/chat/stream", json_body={"query": "问题"})
        )

    assert [event["type"] for event in events] == ["text", "sources", "done"]
    assert events[-1]["session_id"] == "s-1"


def test_stream_request_maps_401_to_authentication_error():
    with ApiClient(
        Profile(),
        token="access-token",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(401, json={"detail": "invalid"})
        ),
    ) as client:
        with pytest.raises(AuthenticationError):
            list(client.stream_request("POST", "/chat/stream", json_body={}))


def _patch_stream_client(monkeypatch, events):
    captured = {}

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream_request(self, method, path, *, json_body=None, **_kwargs):
            captured.update(method=method, path=path, json_body=json_body)
            return iter(events)

    class FakeStore:
        def get_token(self, _profile):
            return _token(int(time.time()) + 3600)

    class FakeConfigStore:
        def get_profile(self, _profile):
            return Profile()

    monkeypatch.setattr(cli, "CredentialStore", FakeStore)
    monkeypatch.setattr(cli, "ConfigStore", FakeConfigStore)
    monkeypatch.setattr(cli, "ApiClient", FakeClient)
    return captured


def test_chat_stream_command_prints_text_and_summary(monkeypatch, capsys):
    _patch_stream_client(
        monkeypatch,
        [
            {"type": "text", "content": "数字地形"},
            {"type": "text", "content": "模型是…"},
            {
                "type": "tool",
                "call_id": "c1",
                "status": "succeeded",
                "tool_name": "pygeomodels.run",
            },
            {"type": "sources", "sources": [{"chunk_id": "c1"}]},
            {
                "type": "done",
                "response": "数字地形模型是…",
                "session_id": "s-1",
                "message_count": 1,
                "sources": [{"chunk_id": "c1"}],
            },
        ],
    )

    assert cli.main(["chat", "stream", "--query", "什么是DTM？", "--use-memory"]) == 0
    captured = capsys.readouterr()

    assert captured.out.startswith("数字地形模型是…")
    assert '"session_id": "s-1"' in captured.out
    assert '"tool_calls"' in captured.out


def test_chat_stream_command_json_output(monkeypatch, capsys):
    _patch_stream_client(
        monkeypatch,
        [
            {"type": "text", "content": "答案"},
            {"type": "done", "response": "答案", "session_id": "s-2"},
        ],
    )

    assert cli.main(["--output", "json", "chat", "stream", "--query", "q"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["result"]["response"] == "答案"
    assert payload["result"]["session_id"] == "s-2"


def test_chat_stream_command_sends_mcp_options(monkeypatch, capsys):
    captured = _patch_stream_client(
        monkeypatch,
        [{"type": "done", "response": "ok", "session_id": "s-3"}],
    )

    assert (
        cli.main(
            [
                "chat",
                "stream",
                "--query",
                "q",
                "--use-mcp",
                "--mcp-server",
                "pygeomodels",
                "--mcp-server",
                "pygeoc",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert captured["path"] == "/chat/stream"
    assert captured["json_body"]["use_mcp"] is True
    assert captured["json_body"]["mcp_servers"] == ["pygeomodels", "pygeoc"]


def test_chat_stream_command_fails_on_error_event(monkeypatch, capsys):
    _patch_stream_client(
        monkeypatch,
        [{"type": "error", "code": 5010, "message": "聊天调用超时"}],
    )

    assert cli.main(["chat", "stream", "--query", "q"]) == 30
    assert "聊天调用超时" in capsys.readouterr().err


def test_session_and_mcp_commands(monkeypatch, capsys):
    captured = {}

    class FakeClient:
        def request_json(self, method, path, **kwargs):
            captured.update(method=method, path=path, **kwargs)
            return {"success": True, "code": 2000, "message": "ok", "data": {}}

    def fake_run_authenticated(args, callback, logger=None):
        cli._success(args, callback(FakeClient()))

    monkeypatch.setattr(cli, "_run_authenticated", fake_run_authenticated)

    assert cli.main(["session", "list"]) == 0
    capsys.readouterr()
    assert captured["method"] == "GET"
    assert captured["path"] == "/chat/sessions"

    assert (
        cli.main(
            [
                "session",
                "history",
                "s-1",
                "--limit",
                "5",
                "--offset",
                "10",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert captured["path"] == "/chat/sessions/s-1/history"
    assert captured["params"] == {"limit": 5, "offset": 10}

    assert cli.main(["session", "rename", "s-1", "--title", "新标题"]) == 0
    capsys.readouterr()
    assert captured["method"] == "POST"
    assert captured["path"] == "/chat/sessions/s-1/rename"
    assert captured["json_body"] == {"title": "新标题"}

    assert cli.main(["mcp", "list"]) == 0
    capsys.readouterr()
    assert captured["path"] == "/mcp/servers"


def test_session_delete_requires_confirmation():
    parser = cli.build_parser()

    args = parser.parse_args(["session", "delete", "s-1"])
    with pytest.raises(cli.ConfigError, match="--yes"):
        cli._require_confirmation(args)
