"""LangChain callbacks for bounded, durable tool-call observability."""

import uuid
from typing import Callable, Optional

from langchain_core.callbacks import BaseCallbackHandler
from sqlalchemy.orm import Session

from app.dao.chat_dao import ChatDAO


class MCPToolLoggingHandler(BaseCallbackHandler):
    """Capture tool lifecycle events without logging full tool inputs or outputs."""

    def __init__(
        self,
        logger,
        request_id: Optional[str] = None,
        db: Optional[Session] = None,
        db_factory: Optional[Callable[[], Session]] = None,
        user_id: Optional[str] = None,
    ):
        self.logger = logger
        self.request_id = request_id
        self.db = db
        self.db_factory = db_factory
        self.user_id = user_id

    def _record(self, callback) -> None:
        """Use a short-lived session so parallel tools never share a session."""
        try:
            if self.db_factory:
                audit_db = self.db_factory()
                try:
                    callback(audit_db)
                finally:
                    audit_db.close()
            elif self.db:
                callback(self.db)
        except Exception:
            self.logger.exception(
                "工具审计记录失败: request_id=%s", self.request_id
            )

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name")
        tool_run_id = str(kwargs.get("run_id") or uuid.uuid4())
        self.logger.info(
            "[TOOL START] request_id=%s tool_run_id=%s tool=%s input=%s",
            self.request_id,
            tool_run_id,
            name,
            ChatDAO._payload_digest(input_str),
        )
        if self.request_id:
            self._record(
                lambda audit_db: ChatDAO.start_tool_run(
                    audit_db,
                    tool_run_id,
                    self.request_id,
                    name,
                    input_str,
                    user_id=self.user_id,
                )
            )

    def on_tool_end(self, output, **kwargs):
        tool_run_id = str(kwargs.get("run_id") or "")
        self.logger.info(
            "[TOOL END] request_id=%s tool_run_id=%s output=%s",
            self.request_id,
            tool_run_id,
            ChatDAO._payload_digest(output),
        )
        if tool_run_id:
            self._record(
                lambda audit_db: ChatDAO.finish_tool_run(
                    audit_db,
                    tool_run_id,
                    "succeeded",
                    output=output,
                    user_id=self.user_id,
                )
            )

    def on_tool_error(self, error, **kwargs):
        tool_run_id = str(kwargs.get("run_id") or "")
        self.logger.error(
            "[TOOL ERROR] request_id=%s tool_run_id=%s error_type=%s error=%s",
            self.request_id,
            tool_run_id,
            type(error).__name__,
            ChatDAO._error_summary(error),
        )
        if tool_run_id:
            self._record(
                lambda audit_db: ChatDAO.finish_tool_run(
                    audit_db,
                    tool_run_id,
                    "failed",
                    error=error,
                    user_id=self.user_id,
                )
            )
