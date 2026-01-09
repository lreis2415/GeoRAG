# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- `FlexibleVectorDB.py`: 灵活向量数据库实现
- `LocalVectorDB.py`: 本地向量数据库实现 (Ollama)
- `DataBase.py`: 基础数据库操作

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