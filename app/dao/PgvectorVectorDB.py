#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
Pgvector 向量数据库实现
使用 langchain-postgres 替代 ChromaDB
"""

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document

from .FlexibleVectorDB import CustomEmbeddings
from .VectorDB import VectorDB

load_dotenv()


class PgvectorVectorDB(VectorDB):
    """
    基于 PostgreSQL pgvector 扩展的向量数据库实现
    使用 langchain-postgres 包 (2025年推荐方案)
    """

    def __init__(
        self,
        connection_string: str,
        db_name: str,
        model_name: str,
        embedding_api_url: str,
        text_splitter_config: Optional[Dict] = None,
    ):
        """
        初始化 PgvectorVectorDB

        Args:
            connection_string: PostgreSQL 连接字符串
            db_name: 知识库名称 (对应 collection_name)
            model_name: 嵌入模型名称
            embedding_api_url: 嵌入模型 API URL
            text_splitter_config: 文本分割器配置
        """
        # 验证必要参数
        if not connection_string:
            raise ValueError("connection_string 不能为空，请确保设置了 DB_URL 环境变量")
        if not db_name:
            raise ValueError("db_name 不能为空")
        if not model_name:
            raise ValueError("model_name 不能为空")
        if not embedding_api_url:
            raise ValueError(
                "embedding_api_url 不能为空，请确保设置了 EMBEDDING_API_URL 环境变量"
            )

        self._connection_string = connection_string
        self._db_name = db_name
        self._model_name = model_name
        self._embedding_api_url = embedding_api_url
        self._text_splitter_config = text_splitter_config or {
            "chunk_size": 1000,
            "chunk_overlap": 200,
        }

        # 创建自定义嵌入函数（复用 FlexibleVectorDB 的实现）
        try:
            self._embeddings = CustomEmbeddings(embedding_api_url, model_name)
            print("✅ PgvectorVectorDB 初始化成功")
            print(f"   数据库: {db_name}")
            print(f"   模型: {model_name}")
        except Exception as e:
            raise ValueError(f"初始化嵌入函数失败: {str(e)}")

    def get_vector_store(self):
        """
        获取 LangChain PGVector 实例

        Returns:
            PGVector 向量存储实例
        """
        try:
            from langchain_postgres import PGVector

            vector_store = PGVector(
                embeddings=self._embeddings,
                collection_name=self._db_name,
                connection=self._connection_string,
                use_jsonb=True,  # 使用 JSONB 存储元数据
            )
            print(f"✅ PGVector 实例创建成功: {self._db_name}")
            return vector_store
        except Exception as e:
            raise RuntimeError(f"创建 PGVector 实例失败: {str(e)}")

    def embed_documents(self, documents: List[Document], batch_size: int = 10) -> None:
        """
        嵌入文档到向量数据库

        Args:
            documents: 文档列表
            batch_size: 批次大小
        """
        try:
            vector_store = self.get_vector_store()

            print(f"🔄 开始嵌入 {len(documents)} 个文档到数据库: {self._db_name}")

            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]
                vector_store.add_documents(batch)
                print(
                    f"   ✅ 批次 {i // batch_size + 1}/"
                    f"{(len(documents) + batch_size - 1) // batch_size} 完成"
                )

            print("✅ 所有文档嵌入完成")
        except Exception as e:
            raise RuntimeError(f"文档嵌入失败: {str(e)}")

    def embed_csv(self, file_path: str) -> None:
        """嵌入 CSV 文件"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import CSVLoader

        loader = CSVLoader(
            file_path=file_path,
            csv_args={"delimiter": ","},
            autodetect_encoding=True,
        )
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_json(self, file_path: str) -> None:
        """嵌入 JSON 文件"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import JSONLoader

        loader = JSONLoader(file_path=file_path, jq_schema=".", text_content=False)
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_txt(self, file_path: str, encoding: str = "utf-8") -> None:
        """嵌入 TXT 文件"""
        try:
            print(f"📄 开始处理 TXT 文件: {file_path}")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")

            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain_community.document_loaders import TextLoader

            print(f"   正在加载文件，编码: {encoding}")
            loader = TextLoader(file_path, encoding=encoding)
            docs = loader.load()
            print(f"   ✅ 文件加载成功，获得 {len(docs)} 个文档")

            print(f"   正在分割文档，配置: {self._text_splitter_config}")
            text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
            documents = text_splitter.split_documents(docs)
            print(f"   ✅ 文档分割完成，共 {len(documents)} 个文档块")

            print("   开始嵌入文档...")
            self.embed_documents(documents)
            print(f"✅ TXT 文件处理完成: {file_path}")

        except Exception as e:
            raise RuntimeError(f"处理 TXT 文件失败 {file_path}: {str(e)}")

    def embed_webpage(self, url: str) -> None:
        """嵌入网页"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import WebBaseLoader

        loader = WebBaseLoader(url, encoding="utf-8")
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def delete_collection(self) -> None:
        """删除当前集合 (知识库)"""
        try:
            vector_store = self.get_vector_store()
            # langchain-postgres 提供的删除方法
            vector_store.delete_collection()
            print(f"✅ 集合 {self._db_name} 已删除")
        except Exception as e:
            raise RuntimeError(f"删除集合失败: {str(e)}")
