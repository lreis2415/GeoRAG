# `/chat/stream` MCP 前端适配方案

## 请求模型

前端只需要为流式聊天请求增加两个可选字段：

```ts
interface ChatStreamRequest {
  prompt: string;
  query: string;
  chat_model_name?: string;
  session_id?: string;
  use_memory?: boolean;
  db_name?: string;
  use_mcp?: boolean;
  mcp_servers?: string[];
}
```

`use_mcp` 有三种发送状态：

| UI 状态 | 请求字段 |
| --- | --- |
| 跟随旧行为 | 省略 `use_mcp` 和 `mcp_servers` |
| 关闭 MCP | `use_mcp: false` |
| 开启 MCP | `use_mcp: true`，按需附带 `mcp_servers` |

开启 MCP 但没有选择具体服务器时，省略 `mcp_servers`，表示使用全部已配置
服务器。不要发送空数组；空数组会被后端视为无效选择。

## UI 交互建议

第一版可提供一个三态控件：`自动`、`关闭`、`开启`。选择“开启”后显示服务器
多选框；不选择具体服务器表示全部服务器。

服务器选项可通过 `GET /llm/v1/mcp/servers` 动态获取：

```json
{
  "initialized": true,
  "servers": [{"name": "pygeomodels"}]
}
```

前端只使用返回的 `name`，不读取或提交 MCP URL。`initialized=false` 时可以展示
服务器名称，但应禁用“开启 MCP”或提示服务尚未就绪。

## SSE 处理

请求地址仍为 `/llm/v1/chat/stream`，已有 SSE 事件格式不变：

- `text`：追加到回答区域。
- `tool`：显示工具调用状态。
- `done`：结束 loading，保存最终回答和 `session_id`。
- `error`：展示错误并结束 loading。

参数校验失败或 MCP 初始化失败可能在建立 SSE 前返回标准 JSON 错误；前端应同时
处理 HTTP 错误响应和 SSE `error` 事件。MCP 连接失败时不要自动重试为“关闭 MCP”，
否则用户会误以为回答未使用工具。

## 状态与兼容性

- 发送“自动”时保持现有前端行为，不修改旧请求生成逻辑。
- 切换“关闭”后，后续请求明确发送 `use_mcp=false`。
- 切换“开启”时，保留用户的服务器选择；切换回“自动”时清空本次请求的
  `mcp_servers` 字段。
- 请求失败时保留用户输入和 MCP 选择，允许用户修改后重试。
- 不在前端日志、错误提示或埋点中记录 Authorization Token。

## 联调检查清单

1. 自动模式请求不包含两个新字段。
2. 关闭模式发送 `use_mcp=false`，服务端不产生 MCP 工具事件。
3. 开启模式发送 `use_mcp=true`，未选择服务器时不发送 `mcp_servers`。
4. 指定服务器时发送服务器名称数组，并能看到正常的 `tool`/`text`/`done` 事件。
5. 发送未知服务器名时正确展示后端参数错误，不进入成功态。
6. 普通 `/chat` 客户端代码无需改动。
