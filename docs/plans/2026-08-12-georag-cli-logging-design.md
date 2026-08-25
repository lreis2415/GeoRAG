# GeoRAG CLI 调用日志设计

## 目标

为 RAG 调优保留 GeoRAG CLI 发出的知识库和问答调用的可复盘记录，同时不
把 access token、密码或上传文件内容写入磁盘。日志必须不改变 CLI 的 JSON
stdout 契约，Agent 仍然只需要读取 stdout。

## 方案

CLI 默认将每次 HTTP 调用追加为一条 JSONL 记录，默认目录为
`~/.local/state/georag/logs/`，文件名按 UTC 日期划分。可以用全局
`--log-dir` 或 `GEORAG_LOG_DIR` 将日志写入某个实验目录；`--no-log` 用于
明确关闭日志。

每条记录包含：schema 版本、run id、开始/结束时间、耗时、服务、HTTP 方法、
path、状态码、请求参数、响应 JSON 和错误信息。`kb ask` 的请求 query、prompt、
知识库名、聊天模型以及服务端返回的完整 `data` 会被记录，便于比较不同
embedding/chat 模型和提示词。multipart 上传只记录字段、文件名和字节数。

字段名匹配 `password`、`token`、`authorization`、`api_key`、`secret` 等敏感
名称时统一替换为 `[REDACTED]`。日志文件和目录分别使用 0600/0700 权限。
日志写入失败只报告到 stderr，不覆盖原始 API 调用结果。

## 验证

- CLI 单元测试验证普通响应、HTTP 错误和超时都会产生结构化日志；
- 测试验证 password/token 不会出现在日志文本中；
- 文档说明日志位置、覆盖方式和安全边界。
