-- ============================================
-- Pgvector 向量数据库初始化脚本
-- 文件位置: db/init/init_vector_tables.sql
-- ============================================

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- LangChain PGVector 会自动创建以下表：
-- langchain_pg_collection: 集合元数据
-- langchain_pg_embedding: 文档和向量嵌入
--
-- 如果需要手动创建或自定义表结构，可以参考以下语句：

-- 1. 为 langchain_pg_collection 表添加 created_at 字段（如果不存在）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'langchain_pg_collection' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE langchain_pg_collection ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END $$;

-- 2. 将 cmetadata 字段从 json 转换为 jsonb（如果存在且为 json 类型）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'langchain_pg_collection' AND column_name = 'cmetadata' AND data_type = 'json'
    ) THEN
        ALTER TABLE langchain_pg_collection ALTER COLUMN cmetadata TYPE JSONB USING cmetadata::JSONB;
    END IF;
END $$;

-- 3. 为 cmetadata 创建 GIN 索引以支持 JSONB 查询
CREATE INDEX IF NOT EXISTS idx_langchain_pg_collection_cmetadata 
    ON langchain_pg_collection USING GIN (cmetadata);

-- 2. 集合元数据表（可选，用于知识库管理）
CREATE TABLE IF NOT EXISTS vector_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    cmetadata JSONB,
    "uuid" UUID UNIQUE DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建 HNSW 索引以优化查询性能（在首次插入数据后自动创建）
-- CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_embedding_vector
--     ON langchain_pg_embedding
--     USING hnsw (embedding_vector vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);

-- 3. 为元数据过滤创建 GIN 索引
-- CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_metadata
--     ON langchain_pg_embedding USING GIN (cmetadata);

-- 4. 为文档内容创建全文搜索索引
-- CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_document
--     ON langchain_pg_embedding USING GIN (to_tsvector('english', document));

-- 注释：以上注释的索引语句会在首次使用 langchain-postgres 时自动创建
--       无需手动执行，仅供参考
