#!/usr/bin/python
# -*- coding:utf-8 -*-
# 使用 Chroma 作为本地向量数据库。
# 使用 Ollama 中的本地模型作为文本嵌入模型。
# 使用TextSplitter将长文档分割成更小的块，便于嵌入和大模型处理。
# 使用tqdm显示嵌入进度。

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from tqdm import tqdm

from langchain.text_splitter import RecursiveCharacterTextSplitter

class LocalVectorDBChroma:
    """使用 Chroma 作为本地向量数据库"""

    def __init__(self,model_name,persist_directory,delimiter = ","):
        self._embedding = OllamaEmbeddings(model=model_name) # 本地模型
        self._persist_directory = persist_directory # 持久存储的本地路径
        self._delimiter = delimiter # CSV 文件的分隔符，默认为逗号

    def get_vector_store(self):
        """从本地路径获取向量数据库"""
        return Chroma(persist_directory=self._persist_directory,embedding_function=self._embedding)

    def embed_documents_in_batches(self,documents,batch_size=3):
        """
        按批次嵌入，可以显示进度。
        向量数据库vectordb会自动持久化存储在磁盘。
        """
        
        vectordb = Chroma(persist_directory=self._persist_directory,embedding_function=self._embedding)
        for i in tqdm(range(0, len(documents), batch_size), desc="嵌入进度"):
            batch = documents[i:i + batch_size]

            # 从文本块生成嵌入，并将嵌入存储在本地磁盘。
            vectordb.add_documents(batch)

    def embed_csv(self,src_file_path):
        """嵌入csv"""

        from langchain_community.document_loaders import CSVLoader
        
        loader = CSVLoader(file_path=src_file_path,
                       csv_args={"delimiter": self._delimiter},
                       autodetect_encoding=True)
        docs = loader.load()

        # 用于将长文本拆分成较小的段，便于嵌入和大模型处理。     
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
        """
        chunk_size: 每个文本块的最大长度/字符数
        chunk_overlap: 拆分的文本块之间重叠字符数
        """
        documents = text_splitter.split_documents(docs) 

        # 耗时较长，需要耐心等候...
        self.embed_documents_in_batches(documents)

    def embed_webpage(self,url):
        """嵌入网页"""

        from langchain_community.document_loaders import WebBaseLoader

        loader = WebBaseLoader(url,encoding="utf-8")    # 增加encoding参数防止中文乱码
        docs = loader.load()
        documents = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        ).split_documents(docs)

        self.embed_documents_in_batches(documents)
    # 嵌入JSON
    def embed_json(self,src_file_path):
        """嵌入JSON
        
        Args:
            src_file_path: JSON文件路径
            
        Returns:
            None: 嵌入结果直接保存到向量数据库
        """
        from langchain_community.document_loaders import JSONLoader
        
        # 设置text_content=False，因为JSON内容是字典而不是字符串
        loader = JSONLoader(
            file_path=src_file_path, 
            jq_schema=".", 
            text_content=False
        )
        docs = loader.load()
        
        # 添加文本分块处理
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200
        )
        documents = text_splitter.split_documents(docs)
        
        self.embed_documents_in_batches(documents)

    # 嵌入TXT
    def embed_txt(self, src_file_path, encoding="utf-8", chunk_size=1000, chunk_overlap=200):
        """嵌入TXT文件到向量数据库
        
        Args:
            src_file_path: TXT文件路径
            encoding: 文件编码，默认为utf-8
            chunk_size: 文本分块大小，默认1000字符
            chunk_overlap: 文本块重叠大小，默认200字符
            
        Returns:
            None: 嵌入结果直接保存到向量数据库
        """
        try:
            from langchain_community.document_loaders import TextLoader
            
            print(f"开始处理TXT文件: {src_file_path}")
            
            # 使用指定编码加载文本文件
            loader = TextLoader(src_file_path, encoding=encoding)
            docs = loader.load()
            
            print(f"文件加载完成，开始文本分块...")
            
            # 文本分块，可自定义分块大小和重叠大小
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, 
                chunk_overlap=chunk_overlap
            )
            documents = text_splitter.split_documents(docs)
            
            print(f"文本分块完成，共{len(documents)}个文本块，开始嵌入...")
            
            # 批量嵌入文档
            self.embed_documents_in_batches(documents)
            
            print(f"TXT文件嵌入完成: {src_file_path}")
            
        except Exception as e:
            print(f"嵌入TXT文件时出错: {str(e)}")
            raise
