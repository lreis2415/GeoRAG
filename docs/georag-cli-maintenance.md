# GeoRAG CLI 维护指南

本文面向需要安装、升级、排障或修改 CLI 的维护者。当前 CLI 只负责
GeoRAG 知识库和文件生命周期操作；实验编排不属于当前版本范围。

## 1. 安装方式

CLI 的 Python 包名是 `georag-cli`，shell 入口是 `georag`。推荐在项目专用
虚拟环境中以 editable 方式安装：

```bash
cd /path/to/GeoRAG
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
command -v georag
georag --help
```

如果使用 Conda，必须在实际运行 CLI 的环境中安装：

```bash
conda activate <environment>
python -m pip install -e /path/to/GeoRAG
```

`python -m pip` 比直接执行 `pip` 更不容易把包装到另一个 Python 环境。
没有 shell 入口时，可以用等价的模块入口诊断：

```bash
python -m georag_cli --help
```

安装入口和运行时依赖由 [setup.py](../setup.py) 声明：

- `httpx`：调用 ModelManager 和 GeoRAG API；
- `keyring`：把访问令牌保存到操作系统凭据存储；
- `console_scripts`：注册 `georag=georag_cli.__main__:main`。

## 2. 端点和 profile 配置

默认端点是：

| 服务 | 默认地址 |
| --- | --- |
| ModelManager | `http://localhost:7504/mbms` |
| GeoRAG | `http://localhost:7512/llm/v1` |

本地 ModelManager 可这样配置：

```bash
georag --profile local config set \
  --modelmanager-url http://127.0.0.1:7504/mbms \
  --georag-url http://127.0.0.1:7512/llm/v1
```

非敏感 profile 配置保存在：

```text
~/.config/georag/config.json
```

可以通过 `GEORAG_CONFIG_PATH` 指定另一份配置文件，适合测试或隔离多个
环境。`GEORAG_MODELMANAGER_URL` 和 `GEORAG_URL` 只用于没有已保存 profile
时的默认值；如果 profile 已经写入 `config.json`，应使用 `config set` 修改。

profile 名称同时是本地凭据的隔离边界，例如 `local` 和 `staging` 会使用
不同的登录令牌。

## 3. API 调用日志

CLI 默认将每次 API 调用追加到结构化 JSONL 日志：

```text
~/.local/state/georag/logs/YYYY-MM-DD.jsonl
```

每条记录包含 run id、服务、HTTP 方法和 path、开始/结束时间、耗时、状态码、
请求参数、原始 JSON 响应和错误信息。携带 `db_name` 的 `chat ask` 请求会保留
query、prompt、知识库名、聊天模型和返回内容，适合比较 RAG 参数。multipart 上传只记录文件名
和大小，不记录文件内容。

指定实验日志目录：

```bash
georag --log-dir ./logs --output json chat ask \
  --db-name <kb-id> --chat-model qwen3.7-flash --query "..."
```

也可以设置 `GEORAG_LOG_DIR`。命令行的 `--log-dir` 优先级高于环境变量；
`--no-log` 可关闭单次调用的日志。日志目录使用 0700，日志文件使用 0600。
password、token、Authorization、API key、secret 等字段会统一替换为
`[REDACTED]`。日志写入失败只输出 stderr 警告，不会覆盖 API 调用结果。

CLI 会记录 `/chat` 返回的 RAG 结果及 `data.sources`；每个来源包含原始文件、
chunk id 和正文。相似度分数和 token 用量当前仍未暴露，若调优需要这些指标，
需要再扩展 Chat API 的响应结构；CLI 日志会自动记录扩展后的字段。

## 4. 认证和凭据存储

登录流程是人工执行一次：

```bash
georag --profile local auth login
georag --profile local auth status
```

CLI 向 ModelManager 的 `/v1/auth/login` 获取 JWT，然后保存到操作系统
Keychain（Keyring service 为 `georag-cli`，account 为 profile 名）。令牌不写入
`config.json`，也不应出现在日志、脚本输出或提交内容中。

当前版本没有 refresh token 自动刷新机制。令牌过期或 API 返回认证错误时，
人工重新执行 `auth login`：

```bash
georag --profile local auth login
```

退出登录应使用：

```bash
georag --profile local auth logout
```

该命令会请求 ModelManager 注销，并删除本地 Keychain 凭据。不要通过编辑
`config.json` 来清理令牌，因为令牌不在那里。

## 5. 代码和 Skill 的职责

| 路径 | 职责 |
| --- | --- |
| `georag_cli/core.py` | profile、Keyring、HTTP 客户端、错误码和响应处理 |
| `georag_cli/__main__.py` | argparse 命令树和 CLI 编排 |
| `tests/test_georag_cli.py` | CLI 单元测试 |
| `docs/georag-cli.md` | 使用者快速上手 |
| `~/.codex/skills/georag-cli/SKILL.md` | Agent 调用约束和推荐工作流 |

修改命令参数、JSON 输出结构、认证行为或删除安全策略时，应同步检查
`SKILL.md`，确保 Agent 使用说明和实际 CLI 一致。新增命令时，先更新 CLI
帮助、单元测试、使用文档，再更新 Skill。

当前 Chat 命令为 `georag chat ask`，将请求发送到 `/chat`。`--db-name` 是
可选参数；省略它时 CLI 不会猜测知识库，而是把选择权交给服务端 Chat/MCP
配置。是否真正发生知识库检索，应通过 JSONL 日志中的 `/chat` 请求/响应和
服务端工具调用信息共同判断。

## 6. 版本和质量检查

版本号目前需要同步修改两个位置：

- `setup.py` 的 `version`；
- `georag_cli/__init__.py` 的 `__version__`。

提交前运行：

```bash
python -m pytest -q tests/test_georag_cli.py
black --check georag_cli tests/test_georag_cli.py
isort --check-only georag_cli tests/test_georag_cli.py
flake8 --max-line-length=88 georag_cli tests/test_georag_cli.py
mypy georag_cli
git diff --check
```

构建本地 wheel 并确认入口：

```bash
python -m pip wheel --no-build-isolation --no-deps .
python -m pip show georag-cli
```

构建生成的 `build/`、`*.egg-info/` 和 wheel 文件不应提交到仓库。

## 7. 常见问题

### `zsh: command not found: georag`

当前 shell 使用的 Python 环境没有安装包，或安装到了另一个环境。执行：

```bash
which python
python -m pip install -e /path/to/GeoRAG
command -v georag
```

### `Profile 'local' does not exist`

自定义 profile 需要先写入端点：

```bash
georag --profile local config set \
  --modelmanager-url http://127.0.0.1:7504/mbms \
  --georag-url http://127.0.0.1:7512/llm/v1
```

### `No saved session` 或退出码 `10`

先人工登录；Agent 后续使用 `--non-interactive --output json` 即可在无提示的
情况下稳定判断认证失败：

```bash
georag --profile local auth login
georag --profile local --non-interactive --output json auth status
```

### `kb ask` 返回 `Request timed out`

CLI 默认 HTTP 超时为 60 秒。问答通常还包含嵌入、检索和聊天模型调用，
端到端耗时可能更长。单次调用可提高超时：

```bash
georag --profile local --timeout 300 --non-interactive --output json \
  kb ask <kb-id> --chat-model qwen3.7-flash --query "..."
```

数据目录端到端脚本默认使用 300 秒，也可以通过 `GEORAG_TIMEOUT` 覆盖：

```bash
GEORAG_TIMEOUT=600 ./scripts/test_georag_cli_data.sh
```
