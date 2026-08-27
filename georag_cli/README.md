# GeoRAG CLI

`georag` 是 GeoRAG 服务端 API 的命令行客户端：带 ModelManager 认证、支持 SSE 流式聊天、知识库/会话/MCP 管理，输出可选 `human` / `json`，适合人工调试和 Agent 脚本化调用。

维护指南见 [docs/georag-cli.md](../docs/georag-cli.md) 与 [docs/georag-cli-maintenance.md](../docs/georag-cli-maintenance.md)。

## 安装与环境

CLI 依赖只有 `httpx` 和 `keyring`，推荐直接装进项目的 conda 环境 `langchain_v03`：

```bash
# 方式 A：conda 环境内安装，获得 georag 命令
conda activate langchain_v03
pip install -e .

# 之后任意目录可用（需先激活环境）
georag --help
```

不想激活环境时，用绝对路径（可写入 ~/.zshrc 作为 alias）：

```bash
alias georag='/opt/homebrew/Caskroom/miniconda/base/envs/langchain_v03/bin/georag'

# 或不装包直接以模块运行（依赖满足即可）
/opt/homebrew/Caskroom/miniconda/base/envs/langchain_v03/bin/python -m georag_cli --help
```

> 注意：全局选项（`--output`、`--profile`、`--timeout` 等）必须写在子命令**之前**，例如 `georag --output json auth status`。

## 配置与认证

```bash
# 端点配置（默认 local profile 指向 localhost:7504/mbms 和 localhost:7512/llm/v1）
georag config set --georag-url http://localhost:7512/llm/v1 --modelmanager-url http://localhost:7504/mbms

# 登录（token 存系统钥匙串，不落盘明文）
georag auth login
georag auth status          # 查看过期时间
georag auth logout
```

- 配置文件：`~/.config/georag/config.json`（可用 `GEORAG_CONFIG_PATH` 覆盖）
- 调用日志：`~/.local/state/georag/logs/YYYY-MM-DD.jsonl`（敏感字段自动脱敏，`--no-log` 关闭）

## 命令一览

| 命令组 | 子命令 | 说明 |
|---|---|---|
| `config` | `set` | 配置端点 profile |
| `auth` | `login` / `status` / `logout` | 登录会话管理 |
| `models` | `list` | 列出可用嵌入/聊天模型 |
| `chat` | `ask` / `stream` | 非流式 / SSE 流式问答 |
| `session` | `list` / `history` / `rename` / `delete` / `clear` | 会话管理 |
| `mcp` | `list` | 列出服务端配置的 MCP 服务器 |
| `kb` | `list` / `show` / `create` / `add` / `files` / `delete` | 知识库管理 |
| `file` | `list` / `download` / `delete` | 源文件管理 |

## 聊天

### 非流式

```bash
georag chat ask --query "什么是数字地形模型？" \
  --db-name geo_knowledge_base \
  --use-memory            # 省略 --session-id 时自动建会话并返回新 id
```

### SSE 流式（推荐）

```bash
georag chat stream --query "帮我把 DEM 转坡度图" \
  --db-name geo_knowledge_base \
  --use-memory \
  --use-mcp \
  --mcp-server pygeomodels \
  --mcp-server pygeoc
```

- `--use-mcp/--no-mcp`：按请求开关 MCP 工具（仅流式接口支持）
- `--mcp-server NAME`：限定使用哪些 MCP 服务器，可重复
- human 模式下答案增量打印到 stdout，`[sources]`/`[tool:...]` 进度走 stderr，结束后输出 session_id / message_count / sources / tool_calls 摘要
- `--output json` 模式缓冲后一次性输出完整结果（含 `response`、`sources`、`tool_calls`）

通用参数：`--prompt`（系统提示词）、`--chat-model`、`--session-id`、`--timeout`。

## 会话管理

```bash
georag session list
georag session history <session_id> --limit 50 --offset 0
georag session rename <session_id> --title "DEM 分析"
georag session delete <session_id> --yes     # 危险操作强制 --yes
georag session clear --yes
```

## MCP

```bash
georag mcp list   # 服务端已配置的 MCP 服务器名称
```

## 知识库与文件

```bash
georag kb list
georag kb create my_kb --embedding-model text-embedding-v4 --file doc.pdf
georag kb add my_kb more.txt
georag kb files my_kb
georag kb delete my_kb --yes

georag file list
georag file download doc.pdf --destination ./out/doc.pdf --force
georag file delete doc.pdf --yes
```

## 输出与退出码

- `--output human`（默认）：结果以缩进 JSON 打印，错误走 stderr
- `--output json`：单行 JSON（`{"ok": true, "result": ...}` / `{"ok": false, "error": ...}`），适合脚本

| exit code | 含义 |
|---|---|
| 0 | 成功 |
| 10 | 未登录 / token 过期或被拒 |
| 20 | 无法连接 API |
| 30 | API 业务或 HTTP 错误 |
| 40 | 本地配置或参数错误 |

## 测试

```bash
/opt/homebrew/Caskroom/miniconda/base/envs/langchain_v03/bin/python -m pytest tests/test_georag_cli.py
```
