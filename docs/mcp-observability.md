# MCP 调用可观测性

每次 `POST /llm/v1/chat` 都会生成一个内部 `request_id`。日志、`chat_runs` 与 `tool_runs` 使用该 ID 关联，不改变既有 API 响应结构。

## 运行状态

- `running`：请求已接收，尚未完成。
- `succeeded`：LLM/Agent 已成功返回。
- `failed`：模型、MCP 或业务逻辑出现异常。
- `timed_out`：超过 `MCP_AGENT_TIMEOUT_SECONDS`（默认 300 秒）。接口返回 HTTP 504。
- `cancelled`：请求协程被取消，例如客户端或上游断开。

用户消息会在 Agent 开始前保存；因此失败请求也能在原会话历史中找到输入。工具审计仅保存字符串字符数（或字节数）及前 4 KB 的 SHA-256 短摘要，不保存原始工具载荷。

## 排查查询

```sql
SELECT request_id, session_id, status, duration_ms, error_type, error_message,
       created_at, finished_at
FROM chat_runs
ORDER BY created_at DESC
LIMIT 50;

SELECT request_id, tool_name, status, input_digest, output_digest, error_message,
       created_at, finished_at
FROM tool_runs
WHERE request_id = '<request_id>'
ORDER BY created_at;
```

## 部署配置

Docker 默认将服务日志写到 `./logs`，并通过以下环境变量控制：

- `LOG_LEVEL`：默认 `INFO`；排障时设为 `DEBUG`。
- `MCP_AGENT_TIMEOUT_SECONDS`：默认 `300`；按最长合理 MCP 调用时长设置。
- `LOG_TO_FILE`：Docker 默认 `true`。

同一 `request_id` 应同时出现在服务日志和两张审计表中。若 `chat_runs` 中没有记录，说明请求未进入聊天路由或审计数据库本身不可用。
