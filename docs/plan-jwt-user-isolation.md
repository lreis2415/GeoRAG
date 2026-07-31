# Plan: JWT authentication and user data isolation

## TODO

- [ ] 1. 将 JWT 认证依赖接入所有受保护路由，并把 `user_id` 从 JWT 传入服务层
- [ ] 2. 为聊天会话、消息和运行审计记录增加 `user_id`
- [ ] 3. 为知识库、文档、向量缓存和文件路径增加用户归属与隔离
- [ ] 4. 增加数据库迁移与兼容处理，避免已有旧数据被错误暴露
- [ ] 5. 补充跨用户隔离测试，并运行认证、DAO、服务和静态检查

## Acceptance Criteria

- 受保护 Agent 接口必须验证 Java 签发的 RS256 JWT。
- Python 只从 JWT `sub` 获取用户 ID，不查询 Java 用户表。
- 聊天、知识库、文档、向量和记忆数据只能被其 `user_id` 所属用户访问。
- 新用户无历史数据时返回空列表或创建新资源，不产生数据库异常。
- 旧数据在无法确认归属时不得暴露给普通用户。
