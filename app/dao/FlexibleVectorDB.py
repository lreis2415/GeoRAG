import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain.embeddings.base import Embeddings
from langchain_core.documents import Document
from openai import OpenAI

from .VectorDB import VectorDB


class CustomEmbeddings(Embeddings):
    """自定义嵌入函数类，实现 LangChain 的 Embeddings 接口"""

    def __init__(self, api_url: str, model_name: str):
        if not api_url:
            raise ValueError(
                "api_url 不能为空，请确保设置了 EMBEDDING_API_URL 环境变量"
            )
        if not model_name:
            raise ValueError("model_name 不能为空")

        self.api_url = api_url
        self.model_name = model_name

        # 从环境变量获取 API key
        load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未找到 OPENAI_API_KEY 环境变量，请确保已正确设置")

        try:
            self.client = OpenAI(api_key=api_key, base_url=api_url)
            # 测试连接
            print("✅ OpenAI 客户端初始化成功")
            print(f"   API URL: {api_url}")
            print(f"   模型名称: {model_name}")
        except Exception as e:
            raise ValueError(f"OpenAI 客户端初始化失败: {str(e)}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """实现文档嵌入方法"""
        try:
            # 分批处理，每批最多10个文本
            batch_size = 10
            all_embeddings = []
            print(f"🔄 开始嵌入 {len(texts)} 个文本，批次大小：{batch_size}")

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(texts) + batch_size - 1) // batch_size
                print(f"   处理批次 {batch_num}/{total_batches}")

                # 使用 OpenAI 客户端创建嵌入
                response = self.client.embeddings.create(
                    model=self.model_name, input=batch
                )

                # 从响应中提取嵌入向量并添加到结果列表
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                print(
                    f"   ✅ 批次 {i//batch_size + 1} 完成，获得 {len(batch_embeddings)} 个嵌入向量"
                )

            print(f"✅ 所有文本嵌入完成，共 {len(all_embeddings)} 个向量")
            return all_embeddings

        except Exception as e:
            error_msg = f"嵌入 API 调用失败: {str(e)}"
            print(f"❌ {error_msg}")
            # 打印更多调试信息
            print(f"   模型名称: {self.model_name}")
            print(f"   API URL: {self.api_url}")
            print(f"   文本数量: {len(texts)}")
            if texts:
                print(f"   首个文本预览: {texts[0][:100]}...")
            raise Exception(error_msg)

    def embed_query(self, text: str) -> List[float]:
        """实现查询嵌入方法"""
        return self.embed_documents([text])[0]


class FlexibleVectorDB(VectorDB):
    """
    一个灵活的向量数据库实现，继承自 VectorDB。
    支持通过 API 调用嵌入模型，并保留 LocalVectorDBChroma 的所有特性。
    """

    def __init__(
        self,
        embedding_api_url: str,
        model_name: str,
        persist_directory: str,
        delimiter: str = ",",
        text_splitter_config: Optional[Dict] = None,
    ):
        """
        初始化 FlexibleVectorDB。

        Args:
            embedding_api_url: 嵌入模型服务的 API 地址。
            model_name: 使用的嵌入模型名称。
            persist_directory: 持久化存储路径。
            delimiter: CSV 文件分隔符，默认为逗号。
            text_splitter_config: 分词器配置。
        """
        # 验证必要参数
        if not embedding_api_url:
            raise ValueError(
                "embedding_api_url 不能为空，请确保设置了 EMBEDDING_API_URL 环境变量"
            )
        if not model_name:
            raise ValueError("model_name 不能为空")
        if not persist_directory:
            raise ValueError("persist_directory 不能为空")

        self._embedding_api_url = embedding_api_url
        self._model_name = model_name
        self._persist_directory = persist_directory
        self._delimiter = delimiter
        self._text_splitter_config = text_splitter_config or {
            "chunk_size": 1000,
            "chunk_overlap": 200,
        }

        # 创建自定义嵌入函数
        try:
            self._embeddings = CustomEmbeddings(embedding_api_url, model_name)
        except Exception as e:
            raise ValueError(f"初始化嵌入函数失败: {str(e)}")

    def get_vector_store(self):
        """获取向量存储"""
        from langchain_chroma import Chroma

        return Chroma(
            persist_directory=self._persist_directory,
            embedding_function=self._embeddings,
        )

    def embed_documents(self, documents: List[Document], batch_size: int = 10) -> None:
        """嵌入文档"""
        from langchain_chroma import Chroma

        vectordb = Chroma(
            persist_directory=self._persist_directory,
            embedding_function=self._embeddings,
        )

        # print(f"开始嵌入 {len(documents)} 个文档")
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            vectordb.add_documents(batch)

    def embed_csv(self, file_path: str) -> None:
        """嵌入 CSV 文件"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
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

            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")

            # 获取文件大小
            file_size = os.path.getsize(file_path)
            print(f"   文件大小: {file_size} 字节")

            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain_community.document_loaders import TextLoader

            # 加载文件
            print(f"   正在加载文件，编码: {encoding}")
            loader = TextLoader(file_path, encoding=encoding)
            docs = loader.load()
            print(f"   ✅ 文件加载成功，获得 {len(docs)} 个文档")

            if docs:
                print(f"   首个文档内容长度: {len(docs[0].page_content)} 字符")
                print(f"   首个文档内容预览: {docs[0].page_content[:200]}...")

            # 分割文档
            print(f"   正在分割文档，配置: {self._text_splitter_config}")
            text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
            documents = text_splitter.split_documents(docs)
            print(f"   ✅ 文档分割完成，共 {len(documents)} 个文档块")

            # 嵌入文档
            print("   开始嵌入文档...")
            self.embed_documents(documents)
            print(f"✅ TXT 文件处理完成: {file_path}")

        except Exception as e:
            error_msg = f"处理 TXT 文件失败 {file_path}: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    def embed_webpage(self, url: str) -> None:
        """嵌入网页"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import WebBaseLoader

        loader = WebBaseLoader(url, encoding="utf-8")
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(**self._text_splitter_config)
        documents = text_splitter.split_documents(docs)
        self.embed_documents(documents)

    def get_document_count(self) -> int:
        """
        获取知识库中的文档数量

        Returns:
            文档数量
        """
        try:
            from langchain_chroma import Chroma

            vectordb = Chroma(
                persist_directory=self._persist_directory,
                embedding_function=self._embeddings,
            )
            return vectordb._collection.count()
        except Exception as e:
            print(f"⚠️ 获取文档数量失败: {e}")
            return 0

    def _get_metadata_file_path(self) -> str:
        """获取元数据文件路径"""
        return os.path.join(self._persist_directory, "metadata.json")

    def get_collection_metadata(self) -> Optional[Dict]:
        """
        获取集合元数据

        Returns:
            元数据字典，如果不存在返回 None
        """
        try:
            metadata_file = self._get_metadata_file_path()
            if os.path.exists(metadata_file):
                with open(metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"⚠️ 获取集合元数据失败: {e}")
            return None

    def update_collection_metadata(self, metadata: Dict) -> None:
        """
        更新集合元数据

        Args:
            metadata: 元数据字典
        """
        try:
            metadata_file = self._get_metadata_file_path()
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"✅ 集合元数据已更新: {metadata_file}")
        except Exception as e:
            raise RuntimeError(f"更新集合元数据失败: {str(e)}")

    def add_files(self, file_paths: List[str]) -> None:
        """
        向知识库添加文件

        Args:
            file_paths: 文件路径列表
        """
        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    raise ValueError(f"文件不存在: {file_path}")

                if file_path.endswith(".csv"):
                    self.embed_csv(file_path)
                elif file_path.endswith(".json"):
                    self.embed_json(file_path)
                elif file_path.endswith(".txt"):
                    self.embed_txt(file_path)
                elif file_path.startswith("http"):
                    self.embed_webpage(file_path)
                else:
                    raise ValueError(f"不支持的文件类型: {file_path}")

            # 更新元数据中的文档数量和文件列表
            metadata = self.get_collection_metadata() or {}
            metadata["document_count"] = self.get_document_count()
            metadata["updated_at"] = datetime.now().isoformat()

            # 更新文件列表：合并现有文件和新文件，去重
            existing_files = metadata.get("files", [])
            new_files = [os.path.basename(fp) for fp in file_paths]
            metadata["files"] = list(set(existing_files + new_files))

            self.update_collection_metadata(metadata)

        except Exception as e:
            raise RuntimeError(f"添加文件失败: {str(e)}")
