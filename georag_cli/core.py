"""Configuration, credentials, and HTTP primitives for the GeoRAG CLI."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4

import httpx
import keyring
from keyring.errors import KeyringError

DEFAULT_MODELMANAGER_URL = "http://localhost:7504/mbms"
DEFAULT_GEORAG_URL = "http://localhost:7512/llm/v1"
KEYRING_SERVICE = "georag-cli"
DEFAULT_LOG_DIR = Path.home() / ".local" / "state" / "georag" / "logs"
_SENSITIVE_LOG_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "password",
    "refresh_token",
    "secret",
    "token",
}
_MAX_LOG_STRING_LENGTH = 2_000_000


class CliError(RuntimeError):
    """Base class for predictable CLI errors."""

    exit_code = 40


class ConfigError(CliError):
    """Raised for invalid local CLI configuration."""


class AuthenticationError(CliError):
    """Raised when a saved credential is missing, expired, or rejected."""

    exit_code = 10


class ApiError(CliError):
    """Raised when a remote API returns a business or HTTP error."""

    exit_code = 30

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConnectivityError(CliError):
    """Raised when an API cannot be reached."""

    exit_code = 20


def _redact_log_value(value: Any, key: Optional[str] = None) -> Any:
    """Make request/response values safe to persist in a local debug log."""
    if key and key.lower() in _SENSITIVE_LOG_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _redact_log_value(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_log_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return {"type": "bytes", "size": len(value)}
    if isinstance(value, str) and len(value) > _MAX_LOG_STRING_LENGTH:
        return {
            "value": value[:_MAX_LOG_STRING_LENGTH],
            "truncated": True,
            "original_length": len(value),
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _summarize_uploads(files: Any) -> Any:
    """Describe multipart files without reading or logging their contents."""
    if files is None:
        return None
    summaries = []
    try:
        items = files.items() if isinstance(files, dict) else files
        for field_name, payload in items:
            filename = None
            file_object: Any = None
            if isinstance(payload, (tuple, list)):
                if payload:
                    filename = payload[0]
                if len(payload) > 1:
                    file_object = payload[1]
            else:
                file_object = payload
            size = None
            if hasattr(file_object, "tell") and hasattr(file_object, "seek"):
                try:
                    position = file_object.tell()
                    file_object.seek(0, os.SEEK_END)
                    size = file_object.tell()
                    file_object.seek(position)
                except (OSError, ValueError):
                    size = None
            summaries.append(
                {
                    "field": str(field_name),
                    "filename": str(filename) if filename is not None else None,
                    "size": size,
                }
            )
    except (TypeError, ValueError):
        return {"type": "multipart", "unavailable": True}
    return summaries


class RequestLogger:
    """Append structured API call records without ever logging credentials."""

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        *,
        command: Optional[str] = None,
        profile: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        configured_dir = os.getenv("GEORAG_LOG_DIR")
        if log_dir is not None:
            self.log_dir = log_dir.expanduser()
        elif configured_dir:
            self.log_dir = Path(configured_dir).expanduser()
        else:
            self.log_dir = DEFAULT_LOG_DIR
        self.command = command
        self.profile = profile
        self.run_id = run_id or uuid4().hex

    @property
    def path(self) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"{date}.jsonl"

    def write(self, record: Dict[str, Any]) -> None:
        payload = {
            "schema_version": 1,
            "event": "api_call",
            "run_id": self.run_id,
            "command": self.command,
            "profile": self.profile,
            **record,
        }
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.log_dir, 0o700)
            log_path = self.path
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        _redact_log_value(payload),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
            os.chmod(log_path, 0o600)
        except OSError as exc:
            # Logging must not turn a successful API operation into a CLI failure.
            print(f"Warning: cannot write CLI log: {exc}", file=sys.stderr)

    def api_call(
        self,
        *,
        started_at: datetime,
        duration_ms: float,
        service: str,
        method: str,
        path: str,
        request: Dict[str, Any],
        status_code: Optional[int] = None,
        response: Any = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.write(
            {
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(duration_ms, 2),
                "service": service,
                "method": method.upper(),
                "path": path,
                "request": request,
                "status_code": status_code,
                "response": response,
                "error": error,
            }
        )


@dataclass
class Profile:
    """Non-secret endpoint configuration for one CLI profile."""

    modelmanager_url: str = DEFAULT_MODELMANAGER_URL
    georag_url: str = DEFAULT_GEORAG_URL

    def normalized(self) -> "Profile":
        return Profile(
            modelmanager_url=self.modelmanager_url.rstrip("/"),
            georag_url=self.georag_url.rstrip("/"),
        )


class ConfigStore:
    """Store endpoint profiles outside the repository and without secrets."""

    def __init__(self, path: Optional[Path] = None) -> None:
        configured_path = os.getenv("GEORAG_CONFIG_PATH")
        self.path = path or (
            Path(configured_path).expanduser()
            if configured_path
            else Path.home() / ".config" / "georag" / "config.json"
        )

    @staticmethod
    def _default_profile() -> Profile:
        return Profile(
            modelmanager_url=os.getenv(
                "GEORAG_MODELMANAGER_URL", DEFAULT_MODELMANAGER_URL
            ),
            georag_url=os.getenv("GEORAG_URL", DEFAULT_GEORAG_URL),
        ).normalized()

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"profiles": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Cannot read config file '{self.path}': {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("profiles", {}), dict
        ):
            raise ConfigError(f"Config file '{self.path}' has an invalid format")
        return payload

    def get_profile(self, name: str) -> Profile:
        payload = self._read()
        saved = payload.get("profiles", {}).get(name)
        if saved is None:
            if name == "local":
                return self._default_profile()
            raise ConfigError(
                f"Profile '{name}' does not exist. "
                f"Run 'georag config set --profile {name} ...'."
            )
        if not isinstance(saved, dict):
            raise ConfigError(f"Profile '{name}' has an invalid format")
        try:
            return Profile(
                modelmanager_url=saved["modelmanager_url"],
                georag_url=saved["georag_url"],
            ).normalized()
        except KeyError as exc:
            raise ConfigError(f"Profile '{name}' is missing {exc.args[0]}") from exc

    def set_profile(
        self,
        name: str,
        *,
        modelmanager_url: Optional[str] = None,
        georag_url: Optional[str] = None,
    ) -> Profile:
        if not modelmanager_url and not georag_url:
            raise ConfigError("Specify --modelmanager-url and/or --georag-url")
        try:
            current = self.get_profile(name)
        except ConfigError:
            if name != "local":
                current = self._default_profile()
            else:
                raise
        profile = Profile(
            modelmanager_url=modelmanager_url or current.modelmanager_url,
            georag_url=georag_url or current.georag_url,
        ).normalized()
        payload = self._read()
        profiles = payload.setdefault("profiles", {})
        profiles[name] = asdict(profile)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ConfigError(f"Cannot write config file '{self.path}': {exc}") from exc
        return profile


class CredentialStore:
    """Keep access tokens in the operating system credential store."""

    def get_token(self, profile_name: str) -> Optional[str]:
        try:
            token = keyring.get_password(KEYRING_SERVICE, profile_name)
            return token if isinstance(token, str) else None
        except KeyringError as exc:
            raise ConfigError(f"Cannot read system credential store: {exc}") from exc

    def save_token(self, profile_name: str, token: str) -> None:
        try:
            keyring.set_password(KEYRING_SERVICE, profile_name, token)
        except KeyringError as exc:
            raise ConfigError(
                f"Cannot save token in system credential store: {exc}"
            ) from exc

    def delete_token(self, profile_name: str) -> None:
        try:
            try:
                keyring.delete_password(KEYRING_SERVICE, profile_name)
            except keyring.errors.PasswordDeleteError:
                return
        except KeyringError as exc:
            raise ConfigError(
                f"Cannot remove token from system credential store: {exc}"
            ) from exc


def token_metadata(token: str) -> Dict[str, Any]:
    """Read untrusted JWT metadata for local expiry/status display only."""
    try:
        encoded_payload = token.split(".")[1]
        padding = "=" * (-len(encoded_payload) % 4)
        payload = base64.urlsafe_b64decode(encoded_payload + padding)
        decoded = json.loads(payload.decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthenticationError("Saved token is not a valid JWT") from exc
    if not isinstance(decoded, dict):
        raise AuthenticationError("Saved token has an invalid payload")
    exp = decoded.get("exp")
    if not isinstance(exp, (int, float)):
        raise AuthenticationError("Saved token does not contain an expiry time")
    return {"sub": decoded.get("sub"), "exp": int(exp)}


def require_active_token(store: CredentialStore, profile_name: str) -> str:
    """Return a non-expired access token or a stable authentication error."""
    token = store.get_token(profile_name)
    if not token:
        raise AuthenticationError("No saved session. Run 'georag auth login'.")
    metadata = token_metadata(token)
    if metadata["exp"] <= int(time.time()):
        raise AuthenticationError("Saved session has expired. Run 'georag auth login'.")
    return token


class ApiClient:
    """Small HTTP client that preserves the server's StandardResponse contract."""

    def __init__(
        self,
        profile: Profile,
        *,
        token: Optional[str] = None,
        timeout: float = 60.0,
        transport: Optional[httpx.BaseTransport] = None,
        logger: Optional[RequestLogger] = None,
    ) -> None:
        self.profile = profile
        self.token = token
        self.logger = logger
        self.client = httpx.Client(
            timeout=timeout, follow_redirects=True, transport=transport
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _headers(self, needs_auth: bool) -> Dict[str, str]:
        if not needs_auth:
            return {}
        if not self.token:
            raise AuthenticationError("No saved session. Run 'georag auth login'.")
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _message_from_response(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip() or f"HTTP {response.status_code}"
        if isinstance(payload, dict):
            return str(payload.get("message") or payload.get("detail") or payload)
        return str(payload)

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        if response.status_code in {401, 403}:
            raise AuthenticationError(
                "Authentication was rejected. Run 'georag auth login'."
            )
        if response.is_error:
            raise ApiError(
                self._message_from_response(response), status_code=response.status_code
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError("API returned an invalid JSON response") from exc
        if not isinstance(payload, dict):
            raise ApiError("API returned an invalid response object")
        if payload.get("success") is False:
            raise ApiError(str(payload.get("message", "API operation failed")))
        return payload

    def request_json(
        self,
        method: str,
        path: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        files: Any = None,
        needs_auth: bool = True,
        modelmanager: bool = False,
    ) -> Dict[str, Any]:
        base_url = (
            self.profile.modelmanager_url if modelmanager else self.profile.georag_url
        )
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        service = "modelmanager" if modelmanager else "georag"
        request_summary = {
            "data": _redact_log_value(data),
            "json": _redact_log_value(json_body),
            "params": _redact_log_value(params),
            "files": _summarize_uploads(files),
        }
        try:
            response = self.client.request(
                method,
                f"{base_url}{path}",
                headers=self._headers(needs_auth),
                params=params,
                data=data,
                json=json_body,
                files=files,
            )
        except httpx.TimeoutException as exc:
            if self.logger:
                self.logger.api_call(
                    started_at=started_at,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    service=service,
                    method=method,
                    path=path,
                    request=request_summary,
                    error={"type": "timeout", "message": str(exc)},
                )
            raise ConnectivityError("Request timed out") from exc
        except httpx.RequestError as exc:
            if self.logger:
                self.logger.api_call(
                    started_at=started_at,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    service=service,
                    method=method,
                    path=path,
                    request=request_summary,
                    error={"type": "request_error", "message": str(exc)},
                )
            raise ConnectivityError(f"Cannot reach API: {exc}") from exc
        response_payload: Any
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = response.text
        if self.logger:
            self.logger.api_call(
                started_at=started_at,
                duration_ms=(time.perf_counter() - started) * 1000,
                service=service,
                method=method,
                path=path,
                request=request_summary,
                status_code=response.status_code,
                response=response_payload,
            )
        return self._handle_response(response)

    def stream_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        needs_auth: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """Stream an SSE endpoint and yield each decoded ``data:`` JSON event."""
        url = f"{self.profile.georag_url}{path}"
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        request_summary = {"json": _redact_log_value(json_body)}
        events: List[Dict[str, Any]] = []

        def log(status_code: Optional[int], error: Optional[Dict[str, Any]]) -> None:
            if not self.logger:
                return
            self.logger.api_call(
                started_at=started_at,
                duration_ms=(time.perf_counter() - started) * 1000,
                service="georag",
                method=method,
                path=path,
                request=request_summary,
                status_code=status_code,
                response={
                    "event_types": [event.get("type") for event in events],
                    "event_count": len(events),
                    "terminal": events[-1] if events else None,
                },
                error=error,
            )

        try:
            with self.client.stream(
                method, url, headers=self._headers(needs_auth), json=json_body
            ) as response:
                if response.status_code in {401, 403}:
                    response.read()
                    log(response.status_code, {"type": "authentication"})
                    raise AuthenticationError(
                        "Authentication was rejected. Run 'georag auth login'."
                    )
                if response.is_error:
                    response.read()
                    message = self._message_from_response(response)
                    log(
                        response.status_code,
                        {"type": "api_error", "message": message},
                    )
                    raise ApiError(message, status_code=response.status_code)
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if not payload:
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        events.append(event)
                        yield event
                log(response.status_code, None)
        except httpx.TimeoutException as exc:
            log(None, {"type": "timeout", "message": str(exc)})
            raise ConnectivityError("Request timed out") from exc
        except httpx.RequestError as exc:
            log(None, {"type": "request_error", "message": str(exc)})
            raise ConnectivityError(f"Cannot reach API: {exc}") from exc

    def download(self, path: str, destination: Path) -> None:
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        try:
            response = self.client.get(
                f"{self.profile.georag_url}{path}", headers=self._headers(True)
            )
        except httpx.TimeoutException as exc:
            if self.logger:
                self.logger.api_call(
                    started_at=started_at,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    service="georag",
                    method="GET",
                    path=path,
                    request={"destination": str(destination)},
                    error={"type": "timeout", "message": str(exc)},
                )
            raise ConnectivityError("Download timed out") from exc
        except httpx.RequestError as exc:
            if self.logger:
                self.logger.api_call(
                    started_at=started_at,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    service="georag",
                    method="GET",
                    path=path,
                    request={"destination": str(destination)},
                    error={"type": "request_error", "message": str(exc)},
                )
            raise ConnectivityError(f"Cannot reach API: {exc}") from exc
        if self.logger:
            self.logger.api_call(
                started_at=started_at,
                duration_ms=(time.perf_counter() - started) * 1000,
                service="georag",
                method="GET",
                path=path,
                request={"destination": str(destination)},
                status_code=response.status_code,
                response={
                    "content_type": response.headers.get("content-type"),
                    "size": len(response.content),
                },
            )
        if "application/json" in response.headers.get("content-type", ""):
            self._handle_response(response)
            raise ApiError("Download endpoint returned JSON instead of a file")
        if response.status_code in {401, 403}:
            raise AuthenticationError(
                "Authentication was rejected. Run 'georag auth login'."
            )
        if response.is_error:
            raise ApiError(
                self._message_from_response(response), status_code=response.status_code
            )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
        except OSError as exc:
            raise ConfigError(f"Cannot write '{destination}': {exc}") from exc
