# Plan: CLI 对齐新版 Chat 接口（SSE 流式 / 会话 / MCP）

## 背景

- conda 环境 `langchain_v03`（`/opt/homebrew/Caskroom/miniconda/base/envs/langchain_v03`，Python 3.11.14）已装 httpx 0.28.1 + keyring，CLI 依赖已满足。
- 服务端 Chat API 在 CLI 完成后新增：`POST /chat/stream` SSE 端点（text/sources/tool/done/error 事件）、`use_mcp`/`mcp_servers` 参数、响应 `sources`/`tool_calls` 字段、`GET /mcp/servers`、会话自动创建与 `/chat/sessions*` 管理接口。
- CLI（`georag_cli/`）目前仅支持非流式 `chat ask`，需对齐。

## TODO

- [ ] 1. 环境接入：在 langchain_v03 中 `pip install -e .` 获得 `georag` 命令；记录免激活 alias 用法（无需改代码）
- [ ] 2. `georag_cli/core.py`：`ApiClient` 新增 `stream_request()` —— httpx 流式请求 + SSE `data:` 行解析为事件生成器，复用认证/错误映射/RequestLogger（记录终止事件摘要）
- [ ] 3. `georag_cli/__main__.py`：新增 `chat stream` 子命令，参数对齐 `ChatStreamRequest`（query/prompt/chat-model/db-name/session-id/use-memory、`--use-mcp/--no-mcp`、可重复 `--mcp-server`）；human 模式增量打印文本、sources/tool 事件走 stderr；json 模式输出 done 事件完整结果；error 事件按现有 exit code 分级退出
- [ ] 4. `georag_cli/__main__.py`：新增 `session` 命令组 `list` / `history <id>` / `rename <id> --title` / `delete <id> --yes` / `clear --yes`
- [ ] 5. `georag_cli/__main__.py`：新增 `mcp list` 命令（GET /mcp/servers）
- [ ] 6. `tests/test_georag_cli.py`：按现有 mock-transport 风格补充 SSE 解析、chat stream、session、mcp 命令用例
- [ ] 7. 新写 CLI 专用 README（`georag_cli/README.md`）：安装（conda/pip install -e/alias 三种方式）、认证流程、全部命令组用法（含新增 chat stream/session/mcp）、输出格式与 exit code、日志与安全说明
- [ ] 8. 引用接入：在 `README.md` 和 `AGENTS.md` 的合适章节（如 README 的功能列表/工具说明、AGENTS.md 的项目概述或常用命令）添加指向 `georag_cli/README.md` 的链接
- [ ] 9. 验证与收尾：langchain_v03 python 跑 pytest；起服务实测 `chat stream` 增量输出；检查 README 链接有效；`pre-commit run --all-files` 通过后提交

## Acceptance Criteria

- `georag chat stream --query ...` 在 human 模式下实时增量输出，结束后展示 session_id/message_count；`--output json` 输出含 response/sources/tool_calls 的完整结果
- `georag chat stream --use-mcp --mcp-server pygeomodels` 能把参数正确写入请求体；服务端返回 error 事件时 CLI 以对应 exit code 退出
- `georag session list|history|rename|delete|clear`、`georag mcp list` 全部可用，delete/clear 强制 `--yes`
- `tests/test_georag_cli.py` 在 langchain_v03 环境全绿
- `georag_cli/README.md` 覆盖环境接入三种方式与全部命令；`README.md`、`AGENTS.md` 中存在指向它的有效链接
