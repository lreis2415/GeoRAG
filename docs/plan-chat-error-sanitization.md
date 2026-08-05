# Plan: chat 接口错误脱敏（欠费模型错误泄漏修复）

## Background

当聊天接口调用的模型欠费（如火山方舟 403 `AllocationQuota.FreeTierOnly`）时，
`app/routers/chat.py` 的通用异常分支将 `str(e)` 直接作为 `message` 返回，
其中包含完整 SDK 错误体（`id`、`request_id`、内部 JSON），泄漏给 API 调用方。

## TODO

- [x] 1. 新增 `app/utils/errors.py`：`safe_error_message(exc, fallback)` 错误清洗助手
      - 识别模式（按优先级）：
        - 额度/欠费：`Free quota exhausted` / `AllocationQuota.FreeTierOnly` /
          `Insufficient Balance` / `insufficient_quota` / `quota` / `欠费` → "Model quota exhausted or account balance insufficient. Please top up your account or contact the administrator."
        - 认证失败：401 / `Invalid API key` / `AuthenticationError` → "Model service authentication failed. Please check your API key configuration."
        - 限流：429 / `Rate limit` → "Model request rate limit exceeded. Please try again later."
        - 模型不存在：`Model not found` / `model_not_found` → "The requested model does not exist or is unavailable."
        - 超时：`timed out` / `timeout` → "Model call timed out. Please try again later."
        - 兜底：`fallback` 参数或 "Internal server error"
      - 原始错误仅用于服务端日志与匹配，绝不进入返回 message
- [x] 2. 修改 `app/routers/chat.py`
      - L245 通用异常分支：`message=safe_error_message(e, fallback="Chat request failed")`，保留 code=5010 与 `logger.exception`
      - 顺带统一其余 `str(e)` 泄漏点（5011/5012/5013/5014/5015）
- [x] 3. 修改 `app/routers/knowledge.py`：同样的 `str(e)` 直传点（嵌入/文档接口）统一走 `safe_error_message`
- [x] 4. 新增 `tests/test_error_sanitization.py`
      - 覆盖额度/认证/限流/模型不存在/未知异常分类
      - 断言返回消息不含原始 JSON、`id`、`request_id`
      - chat 端点 mock 抛 SDK 风格异常，验证响应脱敏、code=5010
- [x] 5. 运行 `pytest tests/test_error_sanitization.py tests/test_chat_api.py` 与 pre-commit 检查

## Acceptance Criteria

- Chat 接口在模型欠费时返回脱敏英文消息，响应不含 `id` / `request_id` / 原始错误 JSON
- 错误响应默认使用英文（`safe_error_message` 各分类与兜底消息）
- 服务端日志（`logger.exception`）仍保留完整原始错误
- 知识库接口同模式脱敏
- 新增测试全部通过，现有测试不回归
