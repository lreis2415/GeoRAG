"""Command-line interface for authenticated GeoRAG access."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from .core import (
    ApiClient,
    ApiError,
    AuthenticationError,
    CliError,
    ConfigError,
    ConfigStore,
    CredentialStore,
    RequestLogger,
    require_active_token,
    token_metadata,
)

DEFAULT_PROMPT = "你是一个地理信息专家助手，请严格基于知识库内容回答问题。"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="georag", description="GeoRAG command-line client"
    )
    parser.add_argument(
        "--profile", default="local", help="endpoint profile (default: local)"
    )
    parser.add_argument(
        "--output", choices=("human", "json"), default="human", help="output format"
    )
    parser.add_argument(
        "--non-interactive", action="store_true", help="fail instead of prompting"
    )
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="HTTP timeout in seconds"
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="directory for structured API logs (default: user state directory)",
    )
    parser.add_argument(
        "--no-log", action="store_true", help="disable structured API logging"
    )
    subparsers = parser.add_subparsers(dest="group", required=True)

    config = subparsers.add_parser("config", help="manage local endpoint profiles")
    config_sub = config.add_subparsers(dest="command", required=True)
    config_set = config_sub.add_parser("set", help="create or update a profile")
    config_set.add_argument("--modelmanager-url")
    config_set.add_argument("--georag-url")

    auth = subparsers.add_parser("auth", help="manage the local login session")
    auth_sub = auth.add_subparsers(dest="command", required=True)
    auth_sub.add_parser("login", help="log in through ModelManager")
    auth_sub.add_parser("status", help="show saved session status")
    auth_sub.add_parser("logout", help="remove the saved session")

    models = subparsers.add_parser("models", help="list available GeoRAG models")
    models_sub = models.add_subparsers(dest="command", required=True)
    models_sub.add_parser("list", help="list embedding and chat models")

    chat = subparsers.add_parser("chat", help="chat through the GeoRAG chat API")
    chat_sub = chat.add_subparsers(dest="command", required=True)
    chat_ask = chat_sub.add_parser("ask", help="send one chat message")
    chat_ask.add_argument("--query", required=True)
    chat_ask.add_argument("--prompt", default=DEFAULT_PROMPT)
    chat_ask.add_argument("--chat-model")
    chat_ask.add_argument("--db-name", help="optional knowledge base for RAG")
    chat_ask.add_argument("--session-id")
    memory_group = chat_ask.add_mutually_exclusive_group()
    memory_group.add_argument(
        "--use-memory", dest="use_memory", action="store_true", default=None
    )
    memory_group.add_argument("--no-memory", dest="use_memory", action="store_false")

    kb = subparsers.add_parser("kb", help="manage knowledge bases")
    kb_sub = kb.add_subparsers(dest="command", required=True)
    kb_sub.add_parser("list", help="list knowledge bases")
    kb_show = kb_sub.add_parser("show", help="show one knowledge base")
    kb_show.add_argument("kb_id")
    kb_create = kb_sub.add_parser("create", help="create a knowledge base")
    kb_create.add_argument("kb_id")
    kb_create.add_argument("--embedding-model", required=True)
    kb_create.add_argument("--file", action="append", type=Path, default=[])
    kb_add = kb_sub.add_parser("add", help="add files to a knowledge base")
    kb_add.add_argument("kb_id")
    kb_add.add_argument("files", nargs="+", type=Path)
    kb_files = kb_sub.add_parser(
        "files", help="list files associated with a knowledge base"
    )
    kb_files.add_argument("kb_id")
    kb_ask = kb_sub.add_parser("ask", help="ask a question against a knowledge base")
    kb_ask.add_argument("kb_id")
    kb_ask.add_argument("--query", required=True)
    kb_ask.add_argument("--prompt", default=DEFAULT_PROMPT)
    kb_ask.add_argument("--chat-model")
    kb_delete = kb_sub.add_parser("delete", help="permanently delete a knowledge base")
    kb_delete.add_argument("kb_id")
    kb_delete.add_argument(
        "--yes", action="store_true", help="confirm permanent deletion"
    )

    files = subparsers.add_parser("file", help="manage uploaded source files")
    files_sub = files.add_subparsers(dest="command", required=True)
    files_sub.add_parser("list", help="list uploaded files")
    file_download = files_sub.add_parser("download", help="download one uploaded file")
    file_download.add_argument("filename")
    file_download.add_argument("--destination", type=Path, required=True)
    file_download.add_argument(
        "--force", action="store_true", help="overwrite destination"
    )
    file_delete = files_sub.add_parser(
        "delete", help="permanently delete one uploaded file"
    )
    file_delete.add_argument("filename")
    file_delete.add_argument(
        "--yes", action="store_true", help="confirm permanent deletion"
    )
    return parser


def _emit(args: argparse.Namespace, payload: Dict[str, Any]) -> None:
    if args.output == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    if payload.get("ok"):
        print(json.dumps(payload.get("result", payload), ensure_ascii=False, indent=2))
    else:
        error = payload.get("error", {})
        print(f"Error: {error.get('message', 'Unknown error')}", file=sys.stderr)


def _success(args: argparse.Namespace, response: Dict[str, Any]) -> None:
    _emit(
        args,
        {
            "ok": True,
            "code": response.get("code"),
            "message": response.get("message"),
            "result": response.get("data"),
        },
    )


def _require_confirmation(args: argparse.Namespace) -> None:
    if not args.yes:
        raise ConfigError("This destructive operation requires --yes")


def _require_existing_files(paths: Iterable[Path]) -> None:
    for path in paths:
        if not path.is_file():
            raise ConfigError(f"File does not exist or is not a regular file: {path}")


def _run_authenticated(
    args: argparse.Namespace,
    callback: Callable[[ApiClient], Dict[str, Any]],
    logger: Optional[RequestLogger] = None,
) -> None:
    profile = ConfigStore().get_profile(args.profile)
    token = require_active_token(CredentialStore(), args.profile)
    with ApiClient(profile, token=token, timeout=args.timeout, logger=logger) as client:
        _success(args, callback(client))


def _handle_config(args: argparse.Namespace) -> None:
    profile = ConfigStore().set_profile(
        args.profile,
        modelmanager_url=args.modelmanager_url,
        georag_url=args.georag_url,
    )
    _emit(args, {"ok": True, "result": profile.__dict__})


def _handle_auth(
    args: argparse.Namespace, logger: Optional[RequestLogger] = None
) -> None:
    store = CredentialStore()
    if args.command == "status":
        token = store.get_token(args.profile)
        if not token:
            _emit(
                args,
                {
                    "ok": False,
                    "error": {
                        "type": "authentication_required",
                        "message": "No saved session. Run 'georag auth login'.",
                    },
                },
            )
            raise SystemExit(AuthenticationError.exit_code)
        metadata = token_metadata(token)
        now = int(datetime.now(timezone.utc).timestamp())
        _emit(
            args,
            {
                "ok": metadata["exp"] > now,
                "result": {
                    "profile": args.profile,
                    "user_id": metadata.get("sub"),
                    "expires_at": datetime.fromtimestamp(
                        metadata["exp"], timezone.utc
                    ).isoformat(),
                    "seconds_remaining": metadata["exp"] - now,
                },
            },
        )
        if metadata["exp"] <= now:
            raise SystemExit(AuthenticationError.exit_code)
        return
    if args.command == "logout":
        profile = ConfigStore().get_profile(args.profile)
        token = store.get_token(args.profile)
        if token:
            try:
                with ApiClient(
                    profile, token=token, timeout=args.timeout, logger=logger
                ) as client:
                    client.request_json("POST", "/v1/account/logout", modelmanager=True)
            except CliError:
                # Removing the local secret remains valuable when remote logout fails.
                pass
        store.delete_token(args.profile)
        _emit(
            args, {"ok": True, "result": {"profile": args.profile, "logged_out": True}}
        )
        return
    if args.non_interactive:
        raise ConfigError("'georag auth login' requires an interactive terminal")
    user_account = input("ModelManager account: ").strip()
    password = getpass.getpass("ModelManager password: ")
    if not user_account or not password:
        raise ConfigError("Account and password are required")
    profile = ConfigStore().get_profile(args.profile)
    with ApiClient(profile, timeout=args.timeout, logger=logger) as client:
        response = client.request_json(
            "POST",
            "/v1/auth/login",
            json_body={"userAccount": user_account, "password": password},
            needs_auth=False,
            modelmanager=True,
        )
    data = response.get("data") or {}
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise ApiError("ModelManager login response did not contain a token")
    metadata = token_metadata(token)
    store.save_token(args.profile, token)
    _emit(
        args,
        {
            "ok": True,
            "result": {
                "profile": args.profile,
                "user_id": data.get("userId") or metadata.get("sub"),
                "username": data.get("username"),
                "expires_at": datetime.fromtimestamp(
                    metadata["exp"], timezone.utc
                ).isoformat(),
            },
        },
    )


def _multipart_files(
    stack: ExitStack, paths: Iterable[Path]
) -> list[tuple[str, tuple[str, Any]]]:
    _require_existing_files(paths)
    return [
        ("files", (path.name, stack.enter_context(path.open("rb")))) for path in paths
    ]


def _handle_models(
    args: argparse.Namespace, logger: Optional[RequestLogger] = None
) -> None:
    _run_authenticated(
        args, lambda client: client.request_json("GET", "/models"), logger
    )


def _handle_chat(
    args: argparse.Namespace, logger: Optional[RequestLogger] = None
) -> None:
    body = {"prompt": args.prompt, "query": args.query}
    if args.chat_model:
        body["chat_model_name"] = args.chat_model
    if args.db_name:
        body["db_name"] = args.db_name
    if args.session_id:
        body["session_id"] = args.session_id
    if args.use_memory is not None:
        body["use_memory"] = args.use_memory
    _run_authenticated(
        args,
        lambda client: client.request_json("POST", "/chat", json_body=body),
        logger,
    )


def _handle_kb(
    args: argparse.Namespace, logger: Optional[RequestLogger] = None
) -> None:
    if args.command == "list":
        _run_authenticated(
            args, lambda client: client.request_json("GET", "/knowledge/bases"), logger
        )
    elif args.command == "show":
        _run_authenticated(
            args,
            lambda client: client.request_json("GET", f"/knowledge/bases/{args.kb_id}"),
            logger,
        )
    elif args.command == "files":
        _run_authenticated(
            args,
            lambda client: client.request_json(
                "GET", f"/knowledge/bases/{args.kb_id}/files"
            ),
            logger,
        )
    elif args.command == "ask":
        body = {
            "db_name": args.kb_id,
            "query": args.query,
            "prompt": args.prompt,
        }
        if args.chat_model:
            body["chat_model_name"] = args.chat_model
        _run_authenticated(
            args,
            lambda client: client.request_json(
                "POST", "/knowledge/ask", json_body=body
            ),
            logger,
        )
    elif args.command == "delete":
        _require_confirmation(args)
        _run_authenticated(
            args,
            lambda client: client.request_json(
                "DELETE", f"/knowledge/bases/{args.kb_id}"
            ),
            logger,
        )
    elif args.command == "create":
        with ExitStack() as stack:
            files = _multipart_files(stack, args.file)
            _run_authenticated(
                args,
                lambda client: client.request_json(
                    "POST",
                    "/knowledge/bases",
                    data={"model_name": args.embedding_model, "db_name": args.kb_id},
                    files=files or None,
                ),
                logger,
            )
    elif args.command == "add":
        with ExitStack() as stack:
            files = _multipart_files(stack, args.files)
            _run_authenticated(
                args,
                lambda client: client.request_json(
                    "POST", f"/knowledge/bases/{args.kb_id}/files", files=files
                ),
                logger,
            )


def _handle_file(
    args: argparse.Namespace, logger: Optional[RequestLogger] = None
) -> None:
    if args.command == "list":
        _run_authenticated(
            args, lambda client: client.request_json("GET", "/knowledge/files"), logger
        )
    elif args.command == "delete":
        _require_confirmation(args)
        _run_authenticated(
            args,
            lambda client: client.request_json(
                "DELETE", f"/knowledge/files/{args.filename}"
            ),
            logger,
        )
    elif args.command == "download":
        if args.destination.exists() and not args.force:
            raise ConfigError(
                f"Destination exists: {args.destination}. Use --force to overwrite."
            )
        profile = ConfigStore().get_profile(args.profile)
        token = require_active_token(CredentialStore(), args.profile)
        with ApiClient(
            profile, token=token, timeout=args.timeout, logger=logger
        ) as client:
            client.download(
                f"/knowledge/files/{args.filename}/download", args.destination
            )
        _emit(args, {"ok": True, "result": {"path": str(args.destination)}})


def run(args: argparse.Namespace) -> None:
    if args.timeout <= 0:
        raise ConfigError("--timeout must be greater than zero")
    logger = None
    if not args.no_log:
        logger = RequestLogger(
            args.log_dir,
            command=f"{args.group}.{getattr(args, 'command', '')}",
            profile=args.profile,
        )
    if args.group == "config":
        _handle_config(args)
    elif args.group == "auth":
        _handle_auth(args, logger)
    elif args.group == "models":
        _handle_models(args, logger)
    elif args.group == "chat":
        _handle_chat(args, logger)
    elif args.group == "kb":
        _handle_kb(args, logger)
    elif args.group == "file":
        _handle_file(args, logger)


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except SystemExit:
        raise
    except CliError as exc:
        _emit(
            args,
            {
                "ok": False,
                "error": {
                    "type": exc.__class__.__name__.replace("Error", "").lower(),
                    "message": str(exc),
                },
            },
        )
        return exc.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
