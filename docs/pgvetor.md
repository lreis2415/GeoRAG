# PostgreSQL pgvector 向量数据库集成指南

本文档介绍如何在 GeoRAG 项目中使用 PostgreSQL 的 pgvector 扩展来实现向量存储功能。

## 1. 环境准备

### 1.1 拉取 pgvector 镜像

pgvector 提供了预配置的 Docker 镜像，集成了 vector 扩展。镜像版本选择参考：[pgvector Docker Hub](https://github.com/pgvector/pgvector?tab=readme-ov-file#docker)

```bash
# 推荐使用 pg14-trixie 版本
docker pull pgvector/pgvector:pg14-trixie
```

### 1.2 启动 PostgreSQL 容器

创建并启动一个专用的 PostgreSQL 容器用于 GeoRAG 项目：

```bash
docker run -d \
  --name georag-postgres \
  -p 5435:5432 \
  -e POSTGRES_USER=geo \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=georag_vector \
  -v pgvector_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg14-trixie
```

**参数说明：**
- `--name`: 容器名称
- `-p 5435:5432`: 将容器的 5432 端口映射到主机的 5435 端口
- `-e POSTGRES_USER`: 数据库用户名
- `-e POSTGRES_PASSWORD`: 数据库密码
- `-e POSTGRES_DB`: 数据库名称
- `-v pgvector_data`: 数据持久化卷

### 1.3 连接数据库

```bash
# 进入容器连接数据库
docker exec -it georag-postgres psql -U geo -d georag_vector
```

## 2. 数据库初始化

### 2.1 启用 vector 扩展

连接到数据库后，创建 pgvector 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2.2 创建数据表结构

创建 RAG 系统所需的数据表：

```sql
-- 数据库元信息表
CREATE TABLE IF NOT EXISTS rag_databases (
    id         SERIAL PRIMARY KEY,
    name       TEXT UNIQUE NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 向量嵌入表
CREATE TABLE IF NOT EXISTS rag_embeddings (
    id          BIGSERIAL PRIMARY KEY,
    db_id       INTEGER NOT NULL REFERENCES rag_databases(id) ON DELETE CASCADE,
    doc_id      TEXT,
    chunk_index INTEGER,
    content     TEXT NOT NULL,
    embedding   vector(1536),  -- 注意：维度需与嵌入模型保持一致
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_rag_embeddings_db_id
    ON rag_embeddings (db_id);

-- 创建向量索引（使用 IVFFlat 算法）
CREATE INDEX IF NOT EXISTS idx_rag_embeddings_embedding
    ON rag_embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
```

**表结构说明：**
- `rag_databases`: 存储向量数据库的元信息
- `rag_embeddings`: 存储文档片段的向量嵌入
- `lists = 100`: IVFFlat 索引参数，可根据数据量调整

## 3. Python 集成实现

### 3.1 安装依赖

在项目依赖中添加 pgvector 相关包：

```toml
# pyproject.toml
[project.dependencies]
pgvector = ">=0.2.0"
psycopg = {version = ">=3.1.0", extras = ["binary"]}
langchain-postgres = ">=0.0.8"
```

### 3.2 实现步骤

#### 3.2.1 创建 PGVectorDB 类

在 `app/dao/PGVectorDB.py` 中实现 PostgreSQL 向量数据库：

```python
from langchain_postgres import PGVector
from .VectorDB import VectorDB

class PGVectorDB(VectorDB):
    """基于 PostgreSQL pgvector 的向量数据库实现"""

    def __init__(
        self,
        connection_string: str,
        db_name: str,
        model_name: str,
        embedding_api_url: str,
    ):
        self.connection_string = connection_string
        self.db_name = db_name
        self.model_name = model_name
        self.embedding_api_url = embedding_api_url
        self._vector_store = None

    def get_vector_store(self) -> PGVector:
        """获取 PGVector 实例"""
        if self._vector_store is None:
            self._vector_store = PGVector(
                connection=self.connection_string,
                embeddings=self.embedding_function,
                collection_name=self.db_name,
                table_name="rag_embeddings",
            )
        return self._vector_store

    # 实现其他抽象方法...
```

#### 3.2.2 修改数据库创建逻辑

在 `database_service.py` 中调整 `create_db` 方法：

```python
# 原始实现（本地文件存储）
# persist_directory = get_persist_directory(db_name)
# vector_db = FlexibleVectorDB(
#     embedding_api_url=embedding_api_url,
#     model_name=model_name,
#     persist_directory=persist_directory,
# )

# 新实现（PostgreSQL 存储）
vector_db = PGVectorDB(
    connection_string=DATABASE_URL,
    db_name=db_name,
    model_name=model_name,
    embedding_api_url=embedding_api_url,
)
```

#### 3.2.3 调整数据库列表获取

修改 `get_all_databases` 方法：

```python
# 原始实现（本地目录遍历）
# databases = []
# for item in os.listdir(database_dir):
#     if os.path.isdir(os.path.join(database_dir, item)):
#         databases.append(item)

# 新实现（数据库查询）
async def get_all_databases(self) -> List[str]:
    """获取所有向量数据库列表"""
    query = "SELECT name FROM rag_databases ORDER BY created_at"
    result = await self.db.fetch_all(query)
    return [row["name"] for row in result]
```

### 3.3 配置更新

在环境变量中添加数据库连接配置：

```bash
# .env
DATABASE_URL=postgresql+psycopg://geo:123456@localhost:5435/georag_vector
```

## 4. 迁移注意事项

### 4.1 数据迁移
- 现有 Chroma 本地数据需要导出并重新导入 PostgreSQL
- 确保嵌入模型一致性，避免维度不匹配

### 4.2 性能优化
- 根据数据量调整 IVFFlat 索引的 `lists` 参数
- 考虑使用连接池管理数据库连接
- 监控查询性能，必要时优化索引策略

### 4.3 备份策略
- 定期备份 PostgreSQL 数据
- 使用 Docker 卷确保数据持久化

## 5. 验证步骤

1. 确认容器正常运行：
   ```bash
   docker ps | grep georag-postgres
   ```

2. 验证数据库连接：
   ```python
   import psycopg
   conn = psycopg.connect(conninfo=DATABASE_URL)
   ```

3. 测试向量插入和查询：
   ```sql
   INSERT INTO rag_databases (name, model_name) VALUES ('test', 'text-embedding-ada-002');
   ```

4. 运行应用测试完整功能

## 6. 故障排查

- **容器启动失败**: 检查端口是否被占用
- **连接失败**: 确认用户名、密码和数据库名正确
- **扩展未找到**: 确保 vector 扩展已创建
- **索引创建失败**: 检查 pgvector 版本兼容性