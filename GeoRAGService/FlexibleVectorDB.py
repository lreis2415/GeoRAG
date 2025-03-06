from .VectorDB import VectorDB
from langchain_core.documents import Document
from typing import List, Optional, Dict
import os
from langchain.embeddings.base import Embeddings
from openai import OpenAI
from dotenv import load_dotenv


class CustomEmbeddings(Embeddings):
    """自定义嵌入函数类，实现 LangChain 的 Embeddings 接口"""
    
    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name
        # 从环境变量获取 API key
        load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未找到 OPENAI_API_KEY 环境变量，请确保已正确设置")
            
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url
        )
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """实现文档嵌入方法"""
        try:
            # 使用 OpenAI 客户端创建嵌入
            response = self.client.embeddings.create(
                model=self.model_name,
                input=texts,
                dimensions=1024,
                encoding_format="float"
            )
            # 从响应中提取嵌入向量
            return [item.embedding for item in response.data]
        except Exception as e:
            raise Exception(f"嵌入 API 调用失败: {str(e)}")
            
    def embed_query(self, text: str) -> List[float]:
        """实现查询嵌入方法"""
        return self.embed_documents([text])[0]

class FlexibleVectorDB(VectorDB):
    """
    一个灵活的向量数据库实现，继承自 VectorDB。
    支持通过 API 调用嵌入模型，并保留 LocalVectorDBChroma 的所有特性。
    """

    def __init__(self, 
                 embedding_api_url: str,
                 model_name: str,
                 persist_directory: str,
                 delimiter: str = ",",
                 text_splitter_config: Optional[Dict] = None):
        """
        初始化 FlexibleVectorDB。

        Args:
            embedding_api_url: 嵌入模型服务的 API 地址。
            model_name: 使用的嵌入模型名称。
            persist_directory: 持久化存储路径。
            delimiter: CSV 文件分隔符，默认为逗号。
            text_splitter_config: 分词器配置。
        """
        self._embedding_api_url = embedding_api_url
        self._model_name = model_name
        self._persist_directory = persist_directory
        self._delimiter = delimiter
        self._text_splitter_config = text_splitter_config or {
            "chunk_size": 1000,
            "chunk_overlap": 200
        }
        self._embeddings = CustomEmbeddings(embedding_api_url, model_name)

    def get_vector_store(self):
        """获取向量存储"""
        from langchain_chroma import Chroma
        return Chroma(
            persist_directory=self._persist_directory,
            embedding_function=self._embeddings
        )

    def embed_documents(self, documents: List[Document], batch_size: int = 32) -> None:
        """嵌入文档"""
        from langchain_chroma import Chroma

        vectordb = Chroma(
            persist_directory=self._persist_directory,
            embedding_function=self._embeddings
        )

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            vectordb.add_documents(batch)

    def embed_csv(self, file_path: str) -> None:
        """嵌入 CSV 文件"""
        from langchain_community.document_loaders import CSVLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        loader = CSVLoader(
            file_path=file_path,
            csv_args={"delimiter": self._delimiter},
            autodetect_encoding=True
        )
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            **self._text_splitter_config
        )
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_json(self, file_path: str) -> None:
        """嵌入 JSON 文件"""
        from langchain_community.document_loaders import JSONLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        loader = JSONLoader(
            file_path=file_path,
            jq_schema=".",
            text_content=False
        )
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            **self._text_splitter_config
        )
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_txt(self, file_path: str, encoding: str = "utf-8") -> None:
        """嵌入 TXT 文件"""
        from langchain_community.document_loaders import TextLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        loader = TextLoader(file_path, encoding=encoding)
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            **self._text_splitter_config
        )
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def embed_webpage(self, url: str) -> None:
        """嵌入网页"""
        from langchain_community.document_loaders import WebBaseLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        loader = WebBaseLoader(url, encoding="utf-8")
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            **self._text_splitter_config
        )
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)