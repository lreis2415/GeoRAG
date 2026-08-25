# Chat MCP 开关与服务器选择设计

## 目标与范围

第一版仅为流式 Chat 接口 `/chat/stream` 增加两个请求字段：

- `use_mcp`：是否启用 MCP。
- `mcp_servers`：启用哪些已配置的 MCP 服务器。

普通 Chat 接口 `/chat` 保持现有请求模型和自动 MCP 行为不变。本版本不支持
单工具筛选、会话级 MCP 配置或请求动态传入 MCP URL。

## 兼容性语义

为了保持现有客户端行为，`use_mcp` 使用三态语义：

| 请求值 | 行为 |
| --- | --- |
| `false` | 禁用 MCP，不初始化或连接 MCP，也不读取用户 MCP Token |
| `true` | 启用 MCP |
| 未提供（`null`） | 保持旧行为：MCP 已初始化且有可用 Token 时自动使用 |

当 `use_mcp=true` 时：

- `mcp_servers` 未提供：使用 `MCP_CONFIG` 中的全部服务器。
- `mcp_servers` 提供：只使用列出的服务器。
- 空数组或未知服务器名称：返回参数错误，不静默降级。

请求只能传服务器名称，服务器 URL、transport、headers 等配置始终来自服务端
`MCP_CONFIG`。

## API 模型

新增仅供 `/chat/stream` 使用的 `ChatStreamRequest`（继承现有聊天字段），在该
模型中增加：

```python
use_mcp: Optional[bool] = Field(
    None,
    description="是否启用 MCP；未提供时保持旧的自动启用行为",
)
mcp_servers: Optional[List[str]] = Field(
    None,
    description="要使用的 MCP 服务器名称；未提供时使用全部已配置服务器",
)
```

示例：

```json
{
  "prompt": "你是一个地理信息专家",
  "query": "查询适合计算坡度的模型",
  "use_mcp": true,
  "mcp_servers": ["pygeomodels"]
}
```

## 服务端数据流

路由层在调用 `ChatService` 前统一解析 MCP 选择：

```text
ChatStreamRequest
  -> 解析 use_mcp / mcp_servers
  -> 校验服务器名称是否在 MCP_CONFIG
  -> MCPService 按服务器子集复制配置
  -> 对选中服务器注入当前用户 Bearer Token
  -> 加载选中服务器的工具
  -> ChatService.chat_with_agent / chat_stream
```

`MCPService.get_mcp_tools_for_token()` 扩展 `server_names` 参数，不能通过
过滤已加载的全量工具来实现服务器选择，因为这样仍可能连接不应使用的服务器。

仅在流式路由中调用 `resolve_stream_mcp_tools()`。普通 `/chat` 不调用该方法，
从而避免普通接口的请求模型和行为发生变化。

## 错误、权限与可观测性

- `use_mcp=false` 与非空 `mcp_servers` 同时出现时返回 `4000`，帮助客户端尽早发现配置错误。
- `mcp_servers` 包含未知名称时返回 `4000`。
- 已配置服务器连接失败时返回 MCP 连接错误，不降级成无 MCP 请求。
- 用户 Token 只注入选中的服务器；请求日志不得记录 Token、完整 headers 或敏感工具参数。
- 日志记录 `request_id`、`use_mcp` 的最终值、选中服务器名称、工具数量和工具名称。
- 首版不改变既有成功响应结构；如后续需要调试信息，再增加可选的 MCP 元数据字段。

## MCP 服务列表接口

新增鉴权只读接口 `GET /llm/v1/mcp/servers`，返回已配置的 MCP 名称和整体
初始化状态：

```json
{
  "initialized": true,
  "servers": [{"name": "pygeomodels"}]
}
```

接口不返回 URL、transport、headers 或 Token。`initialized` 是 MCP 服务整体状态，
不是逐服务器健康检查；前端主要使用 `servers[].name` 构造 `mcp_servers` 请求。

## 测试与实施顺序

1. 为 `ChatStreamRequest` 增加字段及校验测试。
2. 为 `MCPService` 增加服务器子集配置和 Token 注入测试。
3. 测试 `use_mcp=false` 不触发 MCP 初始化或连接。
4. 测试默认兼容行为、全量服务器和指定服务器三种路径。
5. 测试未知服务器、空数组和连接失败的错误路径。
6. 验证普通 `/chat` 的请求模型和行为没有变化。
7. 更新流式 API 文档和请求示例。
8. 所有后端测试通过后，再输出前端适配方案；前端适配不在本次后端实现中。

## 实施状态

- [DONE:1] 已新增仅供 `/chat/stream` 使用的 `ChatStreamRequest`。
- [DONE:2] 已实现 `use_mcp` 三态兼容逻辑和 `mcp_servers` 服务器筛选。
- [DONE:3] 已实现选中服务器的 Token 注入与错误传播。
- [DONE:4] 已补充流式 MCP 选择、兼容行为和服务配置测试。
- [DONE:5] 定向测试已通过；仓库中两个既有 MCP 测试因原有 fixture/依赖版本不匹配失败，
  未在本次范围内修改。
- [DONE:6] 已新增 `GET /llm/v1/mcp/servers` 服务列表接口及测试。
- [DONE:7] 前端适配方案已单独输出。

本设计已确认，后端实现范围为 `/chat/stream`、MCP 服务列表只读接口及其测试。
