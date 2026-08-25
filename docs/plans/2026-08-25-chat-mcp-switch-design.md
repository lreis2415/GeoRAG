# Chat MCP 开关与服务器选择设计

## 目标与范围

第一版为 Chat 接口增加两个请求字段：

- `use_mcp`：是否启用 MCP。
- `mcp_servers`：启用哪些已配置的 MCP 服务器。

本版本不支持单工具筛选、会话级 MCP 配置或请求动态传入 MCP URL。
`/chat` 与 `/chat/stream` 使用同一套选择逻辑。

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

在 `ChatRequest` 中增加：

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
ChatRequest
  -> 解析 use_mcp / mcp_servers
  -> 校验服务器名称是否在 MCP_CONFIG
  -> MCPService 按服务器子集复制配置
  -> 对选中服务器注入当前用户 Bearer Token
  -> 加载选中服务器的工具
  -> ChatService.chat_with_agent / chat_stream
```

`MCPService.get_mcp_tools_for_token()` 扩展 `server_names` 参数，不能通过
过滤已加载的全量工具来实现服务器选择，因为这样仍可能连接不应使用的服务器。

建议抽取路由共用的 `resolve_mcp_tools()` 辅助方法，避免普通和流式接口出现
不同的默认行为。

## 错误、权限与可观测性

- `use_mcp=false` 与非空 `mcp_servers` 同时出现时返回 `4000`，帮助客户端尽早发现配置错误。
- `mcp_servers` 包含未知名称时返回 `4000`。
- 已配置服务器连接失败时返回 MCP 连接错误，不降级成无 MCP 请求。
- 用户 Token 只注入选中的服务器；请求日志不得记录 Token、完整 headers 或敏感工具参数。
- 日志记录 `request_id`、`use_mcp` 的最终值、选中服务器名称、工具数量和工具名称。
- 首版不改变既有成功响应结构；如后续需要调试信息，再增加可选的 MCP 元数据字段。

## 测试与实施顺序

1. 为 `ChatRequest` 增加字段及校验测试。
2. 为 `MCPService` 增加服务器子集配置和 Token 注入测试。
3. 测试 `use_mcp=false` 不触发 MCP 初始化或连接。
4. 测试默认兼容行为、全量服务器和指定服务器三种路径。
5. 测试未知服务器、空数组和连接失败的错误路径。
6. 对 `/chat` 与 `/chat/stream` 验证相同的工具选择结果。
7. 更新 CLI/API 文档和请求示例。

本设计只固化接口与行为约定，不包含本版本的业务代码实现。
