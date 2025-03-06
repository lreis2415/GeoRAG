# GeoRAG 项目

## 项目概述
GeoRAG 是一个基于Retrieval-Augmented Generation (RAG) 技术的地理信息问答系统，提供文档管理、向量数据库管理以及智能问答功能。

## 功能特性
- 文档管理：支持CSV、JSON、TXT格式文件的上传、下载和删除
- 向量数据库管理：支持创建、添加文件、删除和查询向量数据库
- 智能问答：基于RAG技术，结合向量检索和生成模型，提供准确的地理信息问答服务
- 多模型支持：支持多种嵌入模型和聊天模型，可根据需求灵活配置

## 快速开始
1. 确保已安装Python 3.9+，建议版本 3.11
2. 克隆本项目：
   ```bash
   git clone https://github.com/your-repo/GeoRAG.git
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
4. 通过命令行或者添加.env文件配置环境变量：
   ```bash
   export OPENAI_API_KEY=your_api_key
   export OPENAI_API_BASE=your_api_base
   export EMBEDDING_API_URL=your_embedding_api_url
   ```
5. 启动服务：
   ```bash
   python GeoRAGApp.py
   ```


## 使用说明
### 文档管理
- 上传文档：POST /databases/add
- 下载文档：GET /documents/download/{filename}
- 删除文档：DELETE /documents/delete/{filename}
- 列出文档：GET /documents

### 数据库管理
- 创建数据库：POST /create_db
- 添加文件到数据库：POST /databases/add
- 删除数据库：DELETE /databases/{db_name}
- 获取数据库列表：GET /databases

### 智能问答
- 发起问答：POST /ask

## 配置项详解
### 环境变量
- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_API_BASE`: OpenAI API基础URL
- `EMBEDDING_API_URL`: 嵌入模型API URL

### 模型配置（model.yaml文件，可扩展）
嵌入模型：
- llama3.3-70b-instruct
- llama3.1-70b-instruct
- text-embedding-v3

聊天模型：
- qwen-turbo
- deepseek-v3

## API文档
### 数据库管理API
#### 创建数据库
- 方法：POST
- 路径：/create_db
- 参数：
  - model_name: 嵌入模型名称
  - db_name: 数据库名称
  - files: 要上传的文件列表（可选）

#### 添加文件到数据库
- 方法：POST
- 路径：/databases/add
- 参数：
  - db_name: 数据库名称
  - files: 要添加的文件列表

#### 删除数据库
- 方法：DELETE
- 路径：/databases/{db_name}
- 参数：
  - db_name: 数据库名称

#### 获取数据库列表
- 方法：GET
- 路径：/databases

### 文档管理API
#### 上传文档
- 方法：POST
- 路径：/databases/add
- 参数：
  - files: 要上传的文件列表

#### 下载文档
- 方法：GET
- 路径：/documents/download/{filename}
- 参数：
  - filename: 文件名

#### 删除文档
- 方法：DELETE
- 路径：/documents/delete/{filename}
- 参数：
  - filename: 文件名

#### 列出文档
- 方法：GET
- 路径：/documents

### 智能问答API
#### 发起问答
- 方法：POST
- 路径：/ask
- 参数：
  - query: 用户查询
  - db_name: 数据库名称
  - embed_model_name: 嵌入模型名称（可选）
  - chat_model_name: 聊天模型名称（可选）
  - use_api: 是否使用API（可选，默认True）