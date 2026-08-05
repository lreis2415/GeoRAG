# GeoRAG

## 项目概述

GeoRAG 是一个基于 Retrieval-Augmented Generation (RAG) 技术的地理信息问答系统，采用分层架构设计，提供文档管理、向量数据库管理和智能问答功能。

## 功能特性

- **文档管理**：支持 CSV、JSON、TXT 格式文件的上传、下载和删除
- **向量数据库管理**：支持创建、添加文件、删除和查询向量数据库
- **智能问答**：基于 RAG 技术，结合向量检索和生成模型，提供准确的地理信息问答服务
- **多模型支持**：支持多种嵌入模型和聊天模型，可根据需求灵活配置
- **多数据库**：支持 Pgvector 和 ChromaDB 两种向量数据库
- **MCP 工具集成**：集成 Model Context Protocol 工具，扩展系统功能

## 快速开始

### 前置要求

- Python 3.9+ (推荐 3.11)
- Docker (用于容器化部署)

### 安装依赖

```bash
pip install -r requirements.txt
```

### 环境变量配置

创建 `.env` 文件或通过命令行设置：

```bash
export OPENAI_API_KEY=your_api_key
export OPENAI_API_BASE=your_api_base
export EMBEDDING_API_URL=your_embedding_api_url
export DB_URL=postgresql://user:password@host:port/database
export USE_PGVECTOR=true  # 使用 Pgvector (推荐)
# export USE_PGVECTOR=false  # 使用 ChromaDB
export DEFAULT_EMBEDDING_MODEL=text-embedding-v4

# 一键启动脚本 (start-mac.sh / start-win.bat) 使用的 conda 环境名称，
# 不设置时使用脚本默认值 langchain_v03。
export GEORAG_CONDA_ENV=langchain_v03
```

### 启动数据库

**使用 Pgvector 时，需要先启动 PostgreSQL 数据库：**

```bash
# 只启动 PostgreSQL 数据库服务（本地开发模式）
docker-compose up -d postgres

# 验证 pgvector 扩展是否安装成功
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"

# 查看容器日志
docker-compose logs -f postgres
```

> **注意**：本地开发时只需启动 `postgres` 服务，应用通过 `python main.py` 启动。如需完整容器化部署，使用 `docker-compose up -d` 启动所有服务。

**如需重置数据库：**

```bash
# 停止并删除旧容器和数据卷
docker-compose down -v

# 重新启动容器
docker-compose up -d postgres
```

### 启动服务

```bash
# 开发模式启动（推荐）
python main.py

# 或者使用 uvicorn 直接启动
uvicorn main:app --host 0.0.0.0 --port 7512 --reload
```

服务启动后：
- 服务地址：http://0.0.0.0:7512
- API 文档：http://0.0.0.0:7512/docs
- 健康检查：http://0.0.0.0:7512/llm/

### 一键启动

项目提供了两个平台对应的启动脚本：

| 脚本 | 平台 |
|------|------|
| `start-mac.sh` | macOS / Linux |
| `start-win.bat` | Windows |

脚本自动完成以下启动流程：
1. 读取 conda 环境名称（优先级：命令行参数 > 系统环境变量 `GEORAG_CONDA_ENV` > 项目 `.env` 文件 > 默认值 `langchain_v03`）
2. 自动定位 conda 并激活对应环境
3. 检查项目依赖是否完整（缺失时自动安装）
4. 当 `USE_PGVECTOR=true` 时自动检查并启动 Pgvector 数据库容器
5. 启动服务并自动打开浏览器访问 API 文档

**配置环境名称** —— 在本地 `.env` 中增加配置（`.env` 已被 git 忽略，不会入库）：

```bash
# .env
GEORAG_CONDA_ENV=langchain_v03
```

或设置为系统环境变量：

```bash
# macOS / Linux
echo 'export GEORAG_CONDA_ENV=langchain_v03' >> ~/.zshrc && source ~/.zshrc

# Windows（执行一次）
setx GEORAG_CONDA_ENV langchain_v03
```

**启动：**

```bash
# macOS / Linux
./start-mac.sh

# Windows（双击或在 cmd 中运行）
start-win.bat
```

两个脚本均支持可选参数：
- `<env_name>` —— 临时指定其他 conda 环境启动
- `--skip-db` —— 跳过 Pgvector 数据库检查/启动

## 使用说明

### 文档管理

| 功能 | 方法 | 路径 |
|------|------|------|
| 上传文档 | POST | `/llm/documents/upload` |
| 下载文档 | GET | `/llm/documents/download/{filename}` |
| 删除文档 | DELETE | `/llm/documents/{filename}` |
| 列出文档 | GET | `/llm/documents` |

### 数据库管理

| 功能 | 方法 | 路径 |
|------|------|------|
| 创建数据库 | POST | `/llm/databases` |
| 添加文件到数据库 | POST | `/llm/databases/add` |
| 删除数据库 | DELETE | `/llm/databases/{db_name}` |
| 获取数据库列表 | GET | `/llm/databases` |

### 智能问答

| 功能 | 方法 | 路径 |
|------|------|------|
| 发起问答 | POST | `/llm/chat/ask` |
| Agent 问答 | POST | `/llm/chat/agent` |

## 配置项详解

### 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 是 |
| `OPENAI_API_BASE` | OpenAI API 基础 URL | 是 |
| `EMBEDDING_API_URL` | 嵌入模型 API URL | 是 |
| `DB_URL` | PostgreSQL 数据库连接字符串 | 是 (Pgvector) |
| `USE_PGVECTOR` | 向量数据库后端选择 (true=pgvector, false=chromadb) | 否 |
| `DEFAULT_EMBEDDING_MODEL` | 默认嵌入模型 | 否 |

### 模型配置 (models.yaml)

#### 嵌入模型
- `llama3.3-70b-instruct`
- `llama3.1-70b-instruct`
- `text-embedding-v4`

#### 聊天模型
- `qwen-turbo-latest`
- `deepseek-v3`
- `qwen-plus-2025-07-28`
- `qwen3-235b-a22b-instruct-2507`

### 向量数据库后端

#### Pgvector (推荐)
- **优势**：统一 PostgreSQL 技术栈、ACID 事务支持、HNSW 索引高性能
- **配置**：`USE_PGVECTOR=true`
- **要求**：PostgreSQL 16+ with pgvector 扩展

#### ChromaDB (备选)
- **优势**：独立部署、易于测试、向后兼容
- **配置**：`USE_PGVECTOR=false`
- **数据存储**：本地文件系统

## Docker 部署

### 使用 Docker Compose

```bash
# 启动 PostgreSQL 容器 (Pgvector)
docker-compose up -d

# 验证 pgvector 扩展
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

### 使用 Dockerfile

```bash
# 构建并运行 Docker 容器
./run_docker.sh
```

## 代码质量

### Pre-commit 钩子

```bash
# 安装 pre-commit 钩子
pre-commit install

# 手动运行所有检查
pre-commit run --all-files
```

### 代码检查工具

```bash
# 格式化代码
black .

# 排序导入
isort .

# 代码风格检查
flake8 .

# 类型检查
mypy .

# 安全检查
bandit -r .
```

## 项目架构

### 分层架构设计

```
app/
├── routers/          # API 路由层 - 处理 HTTP 请求
├── services/         # 业务逻辑层 - 实现核心功能
├── dao/             # 数据访问层 - 数据库操作
└── utils/           # 工具层 - 配置、异常处理等
```

### 项目结构

```
GeoRAG/
├── .gitignore
├── .pre-commit-config.yaml  # Pre-commit 钩子配置
├── Dockerfile
├── docker-compose.yml       # Docker Compose 配置
├── main.py                  # 主应用程序入口文件
├── models.yaml              # 模型配置文件
├── pyproject.toml           # 代码质量工具配置
├── requirements.txt         # 依赖包列表
├── run_docker.sh            # 运行 Docker 容器的脚本
├── app/                     # 应用核心代码
│   ├── dao/                # 数据访问层
│   │   ├── VectorDB.py          # 向量数据库抽象基类
│   │   ├── PgvectorVectorDB.py  # Pgvector 实现
│   │   ├── FlexibleVectorDB.py  # ChromaDB 实现
│   │   └── DataBase.py          # 基础数据库操作
│   ├── routers/            # API 路由层
│   │   ├── chat.py             # 聊天和问答接口
│   │   ├── databases.py        # 向量数据库管理接口
│   │   ├── documents.py        # 文档管理接口
│   │   ├── models.py           # 模型管理接口
│   │   └── health.py           # 健康检查接口
│   ├── services/           # 业务逻辑层
│   │   ├── chat_service.py      # 聊天服务
│   │   ├── database_service.py  # 数据库服务
│   │   ├── document_service.py  # 文档服务
│   │   ├── model_service.py     # 模型服务
│   │   ├── mcp_service.py       # MCP 工具集成服务
│   │   └── rag_service.py       # RAG 核心服务
│   └── utils/              # 工具层
│       ├── config.py           # 应用配置管理
│       ├── dependencies.py     # 依赖注入
│       ├── exceptions.py       # 异常处理
│       ├── models.py           # 数据模型
│       └── response.py         # 响应格式化
├── data/                  # 数据存储目录
│   ├── documents/         # 文档存储
│   └── database/          # 向量数据库存储 (ChromaDB)
├── tests/                 # 测试文件
└── archive/               # 归档目录
    └── GeoRAGService/     # 旧版代码归档
```

## 注意事项

- API 文档：启动服务后访问 http://0.0.0.0:7512/docs 查看完整的交互式 API 文档
- 文档存储：`data/documents/` 目录
- 向量数据库存储：
  - Pgvector: PostgreSQL 数据库
  - ChromaDB: `data/database/` 目录

## 开发指南

详细开发指南请参考 [CLAUDE.md](./CLAUDE.md) 文件。

## License

MIT License
