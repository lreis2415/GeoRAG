from abc import ABC, abstractmethod
from typing import List, Optional
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

class VectorDB(ABC):
    """
    向量数据库抽象基类
    未来如果需要支持其他向量存储引擎（如Elasticsearch或Pinecone），只需创建新的实现类并继承VectorDB 即可。
    """
    
    @abstractmethod
    def get_vector_store(self) -> VectorStore:
        """获取向量存储"""
        pass
        
    @abstractmethod
    def embed_documents(self, documents: List[Document], batch_size: int = 32) -> None:
        """嵌入文档"""
        pass
        
    @abstractmethod
    def embed_csv(self, file_path: str) -> None:
        """嵌入CSV文件"""
        pass
        
    @abstractmethod
    def embed_json(self, file_path: str) -> None:
        """嵌入JSON文件"""
        pass
        
    @abstractmethod
    def embed_txt(self, file_path: str) -> None:
        """嵌入TXT文件"""
        pass
        
    @abstractmethod
    def embed_webpage(self, url: str) -> None:
        """嵌入网页"""
        pass
