#!/usr/bin/python
# -*- coding:utf-8 -*-
from typing import Dict, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from tqdm import tqdm

from .VectorDB import VectorDB


class LocalVectorDBChroma(VectorDB):
    """使用Chroma作为本地向量数据库的实现"""

    def __init__(
        self,
        model_name: str,
        persist_directory: str,
        delimiter: str = ",",
        text_splitter_config: Optional[Dict] = None,
    ):
        """
        初始化本地向量数据库

        Args:
            model_name: Ollama模型名称
            persist_directory: 持久化存储路径
            delimiter: CSV文件分隔符，默认为逗号
            text_splitter_config: 分词器配置
        """
        self._embedding = OllamaEmbeddings(model=model_name)
        self._persist_directory = persist_directory
        self._delimiter = delimiter
        self._text_splitter_config = text_splitter_config or {
            "chunk_size": 1000,
            "chunk_overlap": 200,
        }

    def get_vector_store(self):
        """获取向量存储"""
        from langchain_chroma import Chroma

        return Chroma(
            persist_directory=self._persist_directory,
            embedding_function=self._embedding,
        )

    def embed_documents(self, documents, batch_size=32):
        """嵌入文档"""
        from langchain_chroma import Chroma

        vectordb = Chroma(
            persist_directory=self._persist_directory,
            embedding_function=self._embedding,
        )

        for i in tqdm(range(0, len(documents), batch_size)):
            batch = documents[i : i + batch_size]
            vectordb.add_documents(batch)

    def embed_csv(self, file_path):
        """嵌入CSV文件"""
        from langchain_community.document_loaders import CSVLoader

        loader = CSVLoader(
            file_path=file_path,
            csv_args={"delimiter": self._delimiter},
            autodetect_encoding=True,
        )
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_json(self, file_path):
        """嵌入JSON文件"""
        from langchain_community.document_loaders import JSONLoader

        loader = JSONLoader(file_path=file_path, jq_schema=".", text_content=False)
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_txt(self, file_path, encoding="utf-8"):
        """嵌入TXT文件"""
        from langchain_community.document_loaders import TextLoader

        loader = TextLoader(file_path, encoding=encoding)
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_webpage(self, url):
        """嵌入网页"""
        from langchain_community.document_loaders import WebBaseLoader

        loader = WebBaseLoader(url, encoding="utf-8")
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)
