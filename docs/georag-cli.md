# GeoRAG CLI

维护 CLI 安装、配置、认证存储和版本发布时，请参阅
[GeoRAG CLI 维护指南](georag-cli-maintenance.md)。

Install the command from this repository:

```bash
pip install -e .
```

The CLI keeps only endpoint profiles in `~/.config/georag/config.json`. It stores the ModelManager access token in the operating system credential store under the `georag-cli` service name.

Configure endpoints when they are not local defaults:

```bash
georag --profile local config set \
  --modelmanager-url http://localhost:7504/mbms \
  --georag-url http://localhost:7512/llm/v1
```

Log in interactively once:

```bash
georag auth login
georag auth status --output json
```

Use the knowledge-base lifecycle commands:

```bash
georag kb create terrain --embedding-model text-embedding-v4 --file ./terrain.txt
georag kb add terrain ./more-data.csv
georag kb files terrain
georag models list
georag kb ask terrain --chat-model <chat-model> --query "DEM 和 DSM 有何区别？"
georag kb delete terrain --yes
```

Call the general Chat API with or without an explicit knowledge base:

```bash
georag --output json chat ask \
  --chat-model qwen3.7-flash \
  --no-memory \
  --query "请判断这个问题应该使用哪个模板。"

georag --output json chat ask \
  --db-name template_dsm_v1 \
  --chat-model qwen3.7-flash \
  --no-memory \
  --query "请按照 DSM 模板提取字段。"
```

Omit `--db-name` to test whether the server-side Chat/MCP configuration can
discover and select a knowledge base. The CLI does not choose a knowledge base
on its own in that mode.

Raw uploaded files are separate resources. Deleting a knowledge base does not delete them:

```bash
georag file list
georag file download server-file.txt --destination ./server-file.txt
georag file delete server-file.txt --yes
```

For an Agent, put global flags before the command and use JSON only:

```bash
georag --non-interactive --output json auth status
georag --non-interactive --output json kb list
```

Every API call is also saved as a structured JSONL record for RAG tuning. The
default location is `~/.local/state/georag/logs/`, and `--log-dir` can redirect
it to an experiment directory:

```bash
georag --log-dir ./logs --output json kb ask terrain \
  --chat-model qwen3.7-flash --query "DEM 和 DSM 有何区别？"
```

The log includes the request, response, model, knowledge-base name, timing and
errors. Passwords, access tokens and API keys are redacted; uploaded files are
represented by filename and size rather than their contents. Use `--no-log` to
disable logging for a specific call.

The CLI does not refresh expired sessions. If it returns exit code `10`, a person must run `georag auth login` again.
