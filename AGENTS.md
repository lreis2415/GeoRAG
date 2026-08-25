# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

GeoRAG 是一个基于 Retrieval-Augmented Generation (RAG) 技术的地理信息问答系统，采用分层架构设计，提供文档管理、向量数据库管理和智能问答功能。

## 开发环境配置

### 前置要求
- Python 3.9+ (推荐 3.11)
- Node.js (使用 nvm 切换到版本 22)：运行 `nvm use 22`
- Docker (可选，用于容器化部署)

### 环境变量配置
项目使用 `.env` 文件管理环境变量，关键配置包括：
- `OPENAI_API_KEY`: OpenAI API 密钥
- `OPENAI_API_BASE`: OpenAI API 基础 URL
- `EMBEDDING_API_URL`: 嵌入模型 API URL
- `DB_URL`: PostgreSQL 数据库连接字符串
- `USE_PGVECTOR`: 向量数据库后端选择 (true=pgvector, false=chromadb)
- `DEFAULT_EMBEDDING_MODEL`: 默认嵌入模型 (text-embedding-v4)

### 依赖安装
```bash
pip install -r requirements.txt
```

### Pre-commit 钩子设置
```bash
# 安装 pre-commit 钩子
pre-commit install

# 手动运行所有检查（所有文件）
pre-commit run --all-files

# 手动运行所有检查（仅暂存文件）
pre-commit run
```

## 常用开发命令

### 启动应用
```bash
# 开发模式启动（推荐）
python main.py

# 或者使用 uvicorn 直接启动
uvicorn main:app --host 0.0.0.0 --port 7512 --reload
```

### 应用信息
- 服务地址：http://0.0.0.0:7512
- API 文档：http://0.0.0.0:7512/docs
- 健康检查：http://0.0.0.0:7512/llm/
- API 前缀：`/llm`

### 代码质量检查
```bash
# 运行所有 pre-commit 检查
pre-commit run --all-files

# 单独运行各工具
black .              # 格式化代码
isort .              # 排序导入
flake8 .             # 代码风格检查
mypy .               # 类型检查
bandit -r .          # 安全检查
```

### Docker 部署
```bash
# 构建并运行 Docker 容器
./run_docker.sh
```

## 项目架构

### 分层架构设计
项目采用清晰的分层架构：

```
app/
├── routers/          # API 路由层 - 处理 HTTP 请求
├── services/         # 业务逻辑层 - 实现核心功能
├── dao/             # 数据访问层 - 数据库操作
└── utils/           # 工具层 - 配置、异常处理等
```

### 核心模块说明

#### 路由层 (routers/)
- `chat.py`: 聊天和问答接口
- `databases.py`: 向量数据库管理接口
- `documents.py`: 文档管理接口
- `models.py`: 模型管理接口
- `health.py`: 健康检查接口

#### 服务层 (services/)
- `rag_service.py`: RAG 核心服务
- `chat_service.py`: 聊天服务
- `database_service.py`: 数据库服务
- `document_service.py`: 文档服务
- `model_service.py`: 模型服务
- `mcp_service.py`: MCP 工具集成服务

#### 数据访问层 (dao/)
- `VectorDB.py`: 向量数据库抽象基类
- `PgvectorVectorDB.py`: PostgreSQL pgvector 向量数据库实现
- `FlexibleVectorDB.py`: ChromaDB 向量数据库实现
- `LocalVectorDB.py`: 本地向量数据库实现 (Ollama)
- `DataBase.py`: 基础数据库操作和工厂函数

#### 工具层 (utils/)
- `config.py`: 应用配置管理
- `exceptions.py`: 异常处理
- `response.py`: 响应格式化
- `dependencies.py`: 依赖注入
- `models.py`: 数据模型

### 模型配置
项目使用 `models.yaml` 文件管理支持的模型：
- **嵌入模型**: llama3.3-70b-instruct, llama3.1-70b-instruct, text-embedding-v4
- **聊天模型**: qwen-turbo-latest, deepseek-v3, qwen-plus-2025-07-28, qwen3-235b-a22b-instruct-2507

## 开发指南

### 代码结构约定
- 使用 FastAPI 框架构建 RESTful API
- 采用依赖注入模式管理服务
- 统一使用 `StandardResponse` 格式化 API 响应
- 使用 Pydantic 模型进行数据验证

### 添加新功能
1. 在 `routers/` 目录添加新的路由文件
2. 在 `services/` 目录实现对应的业务逻辑
3. 在 `utils/models.py` 中定义数据模型
4. 在 `main.py` 中注册新路由

### 异常处理
项目使用统一的异常处理机制：
- 自定义异常类在 `utils/exceptions.py`
- 全局异常处理器在 `main.py` 中注册
- 使用 `StandardResponse` 返回错误信息

### MCP 工具集成
项目集成了 MCP (Model Context Protocol) 工具：
- MCP 服务管理在 `services/mcp_service.py`
- 支持动态工具加载和管理
- 通过依赖注入提供全局 MCP 服务

### 向量数据库配置
项目支持两种向量数据库后端，可通过环境变量切换：

#### Pgvector (推荐)
- **优势**：统一 PostgreSQL 技术栈、ACID 事务支持、HNSW 索引高性能
- **配置**：设置 `USE_PGVECTOR=true`
- **要求**：PostgreSQL 16+ with pgvector 扩展
- **数据存储**：PostgreSQL 数据库

#### ChromaDB (备选)
- **优势**：独立部署、易于测试、向后兼容
- **配置**：设置 `USE_PGVECTOR=false`
- **数据存储**：本地文件系统 (`data/database/`)

#### 切换后端
```bash
# 使用 Pgvector
export USE_PGVECTOR=true

# 使用 ChromaDB
export USE_PGVECTOR=false
```

#### 启动 Pgvector 数据库
```bash
# 停止并删除旧容器
docker-compose down -v

# 启动新容器 (使用 pgvector 镜像)
docker-compose up -d

# 验证 pgvector 扩展
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

## 测试

### 测试文件
- `test_mcp.py`: MCP 服务测试

### 运行测试
```bash
python test_mcp.py
```

## 部署

### 生产环境部署
1. 使用 Docker 容器化部署
2. 配置环境变量
3. 使用 `run_docker.sh` 脚本启动

### 服务端口
- 默认端口：7512
- 可通过环境变量 `PORT` 修改

## 数据库备份与恢复

项目默认使用 Pgvector 向量数据库，数据库运行在 Docker 容器 `georag-postgres` 中（库名 `georag_dev`，用户 `geo`，密码 `123456`，宿主端口 5434 映射容器 5432）。备份文件统一存放在项目根目录 `db_backups/YYYYMMDD_HHMMSS/` 下，该目录已被 git 忽略。

### 导出（备份）

```bash
# 创建备份目录
BACKUP_DIR="db_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 在容器内生成备份文件（两种格式）
docker exec georag-postgres pg_dump -U geo -d georag_dev -Fc -f /tmp/georag_dev.dump  # 压缩格式，恢复用 pg_restore
docker exec georag-postgres pg_dump -U geo -d georag_dev -Fp -f /tmp/georag_dev.sql   # 纯 SQL 格式，可读、可 psql 导入

# 拷贝到本地并清理容器内临时文件
docker cp georag-postgres:/tmp/georag_dev.dump "$BACKUP_DIR/georag_dev.dump"
docker cp georag-postgres:/tmp/georag_dev.sql "$BACKUP_DIR/georag_dev.sql"
docker exec georag-postgres rm -f /tmp/georag_dev.dump /tmp/georag_dev.sql

# 可选：备份全局对象（角色等）
docker exec georag-postgres pg_dumpall -U geo --roles-only -f /tmp/globals.sql
docker cp georag-postgres:/tmp/globals.sql "$BACKUP_DIR/globals.sql"
```

验证备份文件是否有效：

```bash
# 检查压缩格式文件头（应显示 PGDMP 魔法字节 + 版本号）
head -c 8 "$BACKUP_DIR/georag_dev.dump" | xxd

# 检查 SQL 文件是否包含数据（应能看到 COPY 语句）
grep "^COPY public\." "$BACKUP_DIR/georag_dev.sql"
```

### 导入（恢复）

```bash
# 方式 1：从压缩格式恢复（推荐，--clean 会覆盖已有同名对象）
docker exec -i georag-postgres pg_restore -U geo -d georag_dev --clean --if-exists < "$BACKUP_DIR/georag_dev.dump"

# 方式 2：从纯 SQL 恢复
docker exec -i georag-postgres psql -U geo -d georag_dev < "$BACKUP_DIR/georag_dev.sql"
```

注意事项：
- 若恢复到全新容器，需先确保 pgvector 扩展可用（`db/init/init_vector_tables.sql` 会在容器首次启动时自动执行）。
- SQL 备份会把 `search_path` 重置为 `''`，导入遇到 schema 相关错误时，先执行 `SET search_path = public;` 再重试。

## 注意事项

### 文件存储
- 文档存储在 `data/documents/` 目录
- 向量数据库存储在 `data/database/` 目录

### API 版本
- 当前版本：1.0.0
- 使用语义化版本控制

### 开发模式
- 使用 `--reload` 参数启用热重载
- 开发时使用 `python run.py` 启动应用

## 代码质量规范

### 代码风格
- 使用 Black 进行代码格式化（88字符行宽）
- 使用 isort 进行导入排序
- 使用 flake8 进行代码风格检查
- 使用 mypy 进行类型检查
- 使用 bandit 进行安全检查

### 配置文件
- `pyproject.toml`: 所有代码质量工具的配置
- `.pre-commit-config.yaml`: Pre-commit 钩子配置

### Git 工作流
1. 创建功能分支
2. 编写代码
3. 运行 `pre-commit run --all-files` 检查代码质量
4. 如有格式问题，运行 `black .` 和 `isort .` 自动修复
5. 手动修复其他问题
6. 提交代码（pre-commit 钩子会自动运行检查）
7. 推送到远程仓库