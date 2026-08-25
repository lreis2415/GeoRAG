# Plan: MCP 多步调用递归上限与流式消息持久化

## 诊断结论

- [DONE:1] `app/services/chat_service.py:736-740` 的 `agent.astream()` 只传入
  callbacks 和 stream mode，没有传 `recursion_limit`。LangGraph 因此使用默认
  递归上限 25。
- [DONE:2] 多个 MCP 模型逐个调用会形成多轮 ReAct 图循环；当模型继续请求工具
  或一个业务步骤包含多个模型调用时，25 个 graph superstep 会在生成最终答案
  前耗尽，抛出 `GraphRecursionError`。这不等同于网络超时或 MCP 工具异常。
- [DONE:3] `app/routers/chat.py:440-471` 只在流正常结束后调用
  `add_to_memory()` 和 `chat_dao.save_message(..., "assistant", ...)`。
  `GraphRecursionError` 在 `:487-496` 的通用异常分支被转换成 SSE error，因此
  已生成但未结束的 assistant 内容没有持久化。用户消息在 `:337-346` 通常已提交，
  但前端若只依赖成功的 `done` 事件，可能把本地对话视为失败而消失。
- [DONE:4] `ChatRun`/`ToolRun` 已能记录失败和工具摘要，但目前没有保存 partial
  response、递归预算或工具调用序号，排查多步调用仍不够直接。

## TODO

- [DONE:5] 1. 增加可配置且有上限的 Agent graph budget
  - 在 `app/utils/config.py` 增加 `MCP_AGENT_RECURSION_LIMIT`，默认先设为 50，
    同时限制最大允许值，避免用无限增大掩盖模型循环。
  - 在 `chat_service.py` 的 `agent.ainvoke()` 和 `agent.astream()` 都传入
    `config={"recursion_limit": ..., "callbacks": [...]}`，保持同步和流式行为一致。
  - 已将默认值限制为 1-100，并在同步、流式 Agent 调用中统一传入该配置；本阶段
    不改动调用记录和消息持久化逻辑。
  - 后续根据真实任务统计调整默认值；若调用仍持续循环，应优化工具描述、模型
    选择和完成条件，而不是无限提高 limit。

- [ ] 2. 对递归耗尽做稳定的领域错误处理
  - 单独捕获 `langgraph.errors.GraphRecursionError`，返回稳定错误码/消息，例如
    `agent_recursion_limit`，不要当作普通内部异常或网络 timeout。
  - SSE error 中携带 `request_id`、`session_id`、是否有 partial response，方便
    前端保留会话上下文和日志关联；不把供应商原始异常体返回给用户。
  - `ChatRun` 终态记录 `failed`、错误类型 `GraphRecursionError`、limit 和工具
    调用摘要。

- [ ] 3. 让失败的流式调用也可恢复
  - 将成功/超时/递归耗尽/取消的收尾逻辑抽成幂等 helper，保证 `ChatRun` 只终结
    一次，并且所有异常路径都执行。
  - 为消息增加明确的未完成状态（推荐给 `ChatMessage` 增加 `status` 或
    `is_complete`，默认 `completed`；同步 ORM、迁移和历史响应模型）。
  - 在递归耗尽或超时时保存已产生的 partial assistant 内容；没有内容时至少保留
    可见的失败状态和 `request_id`，避免前端误认为整条会话不存在。
  - 前端/历史接口应能区分 `completed`、`failed`、`cancelled`，而不是把失败消息
    当作成功回答展示。

- [ ] 4. 增强 MCP 调用可观测性
  - 为每个 ToolRun 保存 step/index、工具名、开始/结束时间、状态和 bounded digest；
    不记录完整工具输入输出中的敏感数据。
  - 在服务端日志打印 request_id、session_id、recursion limit、当前 step 和工具
    名称，便于确认是合法长链还是工具循环。
  - 针对“连续逐个模型调用”的请求，确认每个工具返回可让模型判断是否完成，必要
    时增加显式的终止指令/完成 schema。

- [ ] 5. 增加回归测试和真实验证
  - 单元测试：mock agent 在第 26/第 N 个 superstep 抛出 `GraphRecursionError`，
    验证 config limit 被传入、错误被识别、ChatRun 终结且 partial message 被保存。
  - 流式测试：覆盖正常完成、递归耗尽、超时、客户端取消、无 token 输出和
    `use_memory=false`（后者按设计不保存会话消息）。
  - MCP 集成测试：复现用户的“分类检索 → 多个模型检索 → 参数查询”链路，验证
    在合理预算内完成；故意超过预算时，历史会话仍可见且状态为 failed。
  - 运行现有 chat/MCP/错误脱敏测试及数据库迁移检查。

## 验收标准

- 多个 MCP 模型调用在预算内可以正常结束，默认 25 的隐式限制不再阻断合法链路。
- 真正的工具循环会在明确预算处停止，并返回可理解、可关联的错误，而不是伪装成
  普通 timeout。
- 递归耗尽、超时或客户端取消后，session、user message、partial assistant message
  或失败状态仍可从历史接口查询。
- `ChatRun`/`ToolRun` 能按 request_id 还原调用次数、工具序列、终态和错误原因。
- 不记录 access token、模型 API key、完整敏感工具 payload；现有错误脱敏行为不回归。
