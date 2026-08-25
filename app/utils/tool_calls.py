"""Safe, user-facing MCP tool-call lifecycle helpers."""

import re
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_PUBLIC_TOOL_KEYS = {
    "pygeomodels_search": "geo.model_search",
    "pygeomodels_get_model": "geo.model_detail",
}
_DEFAULT_TOOL_KEY = "mcp.tool"
_RAG_TOOL_NAMES = {"info_retriever"}
_PUBLIC_TOOL_SOURCES = {"mcp", "rag"}
_DEFAULT_FAILURE_CODE = "mcp.tool_failed"
_PUBLIC_ERROR_CODES = {
    _DEFAULT_FAILURE_CODE,
    "mcp.agent_failed",
    "mcp.cancelled",
    "mcp.execution_incomplete",
    "mcp.timed_out",
}


def public_tool_key(tool_name: object) -> str:
    """Map an internal tool name to an allowlisted public presentation key."""
    return _PUBLIC_TOOL_KEYS.get(str(tool_name or ""), _DEFAULT_TOOL_KEY)


def is_safe_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER_RE.fullmatch(value))


def public_tool_name(tool_name: object) -> Optional[str]:
    """Return a displayable identifier without exposing arguments or output."""
    return str(tool_name) if is_safe_identifier(tool_name) else None


def public_tool_source(tool_name: object, source: object = None) -> str:
    """Classify tools by their registered execution source for UI display."""
    if source in _PUBLIC_TOOL_SOURCES:
        return str(source)
    return "rag" if public_tool_name(tool_name) in _RAG_TOOL_NAMES else "mcp"


def normalize_tool_calls(value: object) -> List[Dict[str, Any]]:
    """Return only valid, terminal, UI-safe tool-call records."""
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        if not isinstance(item, dict):
            continue
        call_id = item.get("id")
        tool_key = item.get("tool_key")
        tool_name = item.get("tool_name")
        tool_source = item.get("tool_source")
        status = item.get("status")
        sequence = item.get("sequence")
        if (
            not is_safe_identifier(call_id)
            or tool_key
            not in set(_PUBLIC_TOOL_KEYS.values()) | {_DEFAULT_TOOL_KEY}
            or status not in {"succeeded", "failed"}
            or not isinstance(sequence, int)
            or sequence < 1
        ):
            continue

        record: Dict[str, Any] = {
            "id": call_id,
            "sequence": sequence,
            "tool_key": tool_key,
            "status": status,
        }
        duration_ms = item.get("duration_ms")
        if isinstance(duration_ms, int) and duration_ms >= 0:
            record["duration_ms"] = duration_ms
        if public_tool_name(tool_name):
            record["tool_name"] = public_tool_name(tool_name)
        record["tool_source"] = public_tool_source(tool_name, tool_source)
        code = item.get("code")
        if status == "failed":
            record["code"] = (
                code if code in _PUBLIC_ERROR_CODES else _DEFAULT_FAILURE_CODE
            )
        normalized.append(record)

    return normalized


class ToolCallTracker:
    """Build ordered, safe events for one streamed chat request."""

    def __init__(self):
        self._calls: Dict[str, Dict[str, Any]] = {}
        self._sequence = 0

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _new_call_id(self, requested_id: object) -> str:
        if (
            is_safe_identifier(requested_id)
            and requested_id not in self._calls
        ):
            return requested_id
        return uuid.uuid4().hex

    def start(self, tool_calls: Iterable[object]) -> List[Dict[str, Any]]:
        """Register complete Agent tool-call objects and emit starts once."""
        events = []
        for raw_call in tool_calls:
            if not isinstance(raw_call, dict) or not raw_call.get("name"):
                continue
            requested_id = raw_call.get("id")
            if (
                is_safe_identifier(requested_id)
                and requested_id in self._calls
            ):
                continue
            call_id = self._new_call_id(requested_id)
            tool_key = public_tool_key(raw_call.get("name"))
            tool_name = public_tool_name(raw_call.get("name"))
            tool_source = public_tool_source(raw_call.get("name"))
            self._calls[call_id] = {
                "id": call_id,
                "tool_key": tool_key,
                "tool_name": tool_name,
                "tool_source": tool_source,
                "status": "started",
                "started_at": time.monotonic(),
                "sequence": 0,
            }
            sequence = self._next_sequence()
            self._calls[call_id]["sequence"] = sequence
            events.append(
                {
                    "type": "tool",
                    "call_id": call_id,
                    "sequence": sequence,
                    "status": "started",
                    "tool_key": tool_key,
                    "tool_name": tool_name,
                    "tool_source": tool_source,
                }
            )
        return events

    def finish(
        self,
        call_id: object,
        tool_name: object = None,
        failed: bool = False,
        code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Finish a call once, adding a safe start if the stream omitted it."""
        if not is_safe_identifier(call_id) or call_id not in self._calls:
            start_events = self.start(
                [{"id": call_id, "name": tool_name or _DEFAULT_TOOL_KEY}]
            )
            if not start_events:
                return []
            call_id = start_events[0]["call_id"]
        else:
            start_events = []

        call = self._calls[call_id]
        if call["status"] != "started":
            return start_events

        status = "failed" if failed else "succeeded"
        sequence = self._next_sequence()
        duration_ms = max(
            0, int((time.monotonic() - call["started_at"]) * 1000)
        )
        call.update(status=status, sequence=sequence, duration_ms=duration_ms)
        if status == "failed":
            call["code"] = (
                code if code in _PUBLIC_ERROR_CODES else _DEFAULT_FAILURE_CODE
            )

        event: Dict[str, Any] = {
            "type": "tool",
            "call_id": call_id,
            "sequence": sequence,
            "status": status,
            "tool_key": call["tool_key"],
            "tool_name": call["tool_name"],
            "tool_source": call["tool_source"],
            "duration_ms": duration_ms,
        }
        if status == "failed":
            event["code"] = call["code"]
        return [*start_events, event]

    def finish_message(self, message: object) -> List[Dict[str, Any]]:
        """Convert a LangChain ToolMessage to a terminal safe event."""
        status = getattr(message, "status", "success")
        return self.finish(
            getattr(message, "tool_call_id", None),
            getattr(message, "name", None),
            failed=status == "error",
            code=_DEFAULT_FAILURE_CODE,
        )

    def fail_pending(self, code: str) -> List[Dict[str, Any]]:
        """Close all non-terminal calls with one safe error code."""
        events = []
        for call_id, call in list(self._calls.items()):
            if call["status"] == "started":
                events.extend(self.finish(call_id, failed=True, code=code))
        return events

    def completed_calls(self) -> List[Dict[str, Any]]:
        """Return validated terminal records for message persistence."""
        return normalize_tool_calls(
            [
                {
                    key: value
                    for key, value in call.items()
                    if key != "started_at"
                }
                for call in self._calls.values()
                if call["status"] in {"succeeded", "failed"}
            ]
        )
