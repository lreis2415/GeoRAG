# Plan: 模型列表完全动态化（从 new-api 网关拉取）

## 背景

接入 new-api 网关后，模型的真实可用性由网关渠道决定，但 GeoRAG 的模型列表仍读静态
`models.yaml`，两边脱节：网关新增模型 GeoRAG 感知不到；GeoRAG 列表里的模型网关没有
（如 `qwen-turbo-latest`），请求直接 502。

方案：`ModelService` 优先从网关的 OpenAI 兼容端点 `GET {OPENAI_API_BASE}/models`
动态拉取模型列表（带 TTL 缓存），按命名约定区分 chat / embedding 模型，网关不可达时
回退 `models.yaml`。顺带修复 `qwen-turbo-latest` 硬编码默认值（共 4 处，该模型已不存在）。

## 依赖的现状事实

- `app/utils/dependencies.py:21` `get_model_service` 带 `@lru_cache`，是单例 → 实例级 TTL 缓存有效
- `app/routers/models.py:15` `GET /llm/models` 直接调用 `get_available_embedding_models()` / `get_available_chat_models()`（每请求都调）
- 模型校验入口：`app/routers/chat.py:82`、`chat.py:356`（chat）、`app/routers/knowledge.py:124`（embedding）
- `qwen-turbo-latest` 硬编码：`app/services/model_service.py:20`、`app/services/chat_service.py:483,586,736`
- 网关 `GET /v1/models`（Bearer 令牌）返回渠道聚合模型，已实测可用；`requirements.txt` 已有 `httpx`

## TODO

- [ ] 1. `app/services/model_service.py`：新增 `_fetch_gateway_models()`（httpx 同步调用，
      timeout 3s），实例级 TTL 缓存（300s，`threading.Lock` 防并发击穿）；
      `get_available_embedding_models()` / `get_available_chat_models()` 改为：
      - `MODEL_SOURCE=yaml` 时维持现状（直读 models.yaml）
      - 默认（gateway）时取网关列表：名字含 `embedding`（不区分大小写）归嵌入模型，其余归 chat
      - 拉取失败或**分类后嵌入模型为空**时回退 models.yaml，并按 TTL 周期记录一次 warning（避免刷屏）
      - 新增 `refresh(force=False)` 参数供手动刷新
- [ ] 2. 修复默认模型硬编码：`default_chat_model` 改为读 `DEFAULT_CHAT_MODEL` 环境变量、
      兜底 `qwen3.7-plus`（网关与 yaml 均存在）；`chat_service.py:483,586,736` 三处同步替换
- [ ] 3. `app/routers/models.py`：`GET /llm/models` 增加 `?refresh=true` 跳过 TTL 缓存，
      响应 data 增加 `source` 字段（`gateway` / `yaml`）便于前端与排查
- [ ] 4. `.env.example` 增加 `MODEL_SOURCE=gateway`、`DEFAULT_CHAT_MODEL=qwen3.7-plus` 及注释
- [ ] 5. 验证（见验收标准），跑 `pre-commit run --all-files`

## 验收标准

- `GET /llm/models` 返回网关聚合的模型（chat 5 个、embedding 1 个），data.source == "gateway"
- 在 new-api 渠道里临时增删一个模型后，`GET /llm/models?refresh=true` 立即反映变化，无需重启应用
- `docker stop one-api` 后 `GET /llm/models` 仍 200，返回 models.yaml 列表（llama3.x、glm-5.2 等），
  source == "yaml"，日志出现一次 fallback warning
- 不带 `chat_model_name` 的聊天请求落到 `qwen3.7-plus`，不再出现 `qwen-turbo-latest` 502
- 知识库创建（`knowledge.py:124` 的 embedding 校验）在网关模式下用 `text-embedding-v4` 通过
- `MODEL_SOURCE=yaml` 时行为与改动前完全一致

## 约束与边界情况

- 网关 `/v1/models` 不返回模型类型信息，chat/embedding 分类只能靠命名约定
  （含 `embedding`）；若分类结果嵌入模型为空，整体回退 yaml 而非返回空列表（保护知识库链路）
- httpx 同步调用阻塞时长受 3s timeout 限制，且 TTL 缓存保证稳态下每 5 分钟最多一次真实请求
- 缓存与锁都在 ModelService 实例上，依赖 `lru_cache` 单例；不引入新的进程级全局状态
