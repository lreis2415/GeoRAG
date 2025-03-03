#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import shutil
from typing import Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from VectorDB import VectorDB
from LocalVectorDB import LocalVectorDBChroma

# 加载环境变量
load_dotenv()
openai_api_key = os.environ.get("QWEN_API_KEY")
openai_api_base = os.environ.get("QWEN_API_BASE")

# 配置路径
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)
current_dir = os.path.dirname(os.path.abspath(__file__))
documents_dir = os.path.join(current_dir, 'documents')
database_dir = os.path.join(current_dir, 'database')

# 确保目录存在
os.makedirs(documents_dir, exist_ok=True)
os.makedirs(database_dir, exist_ok=True)

def get_persist_directory(db_name: str) -> str:
    """获取向量数据库存储路径"""
    db_name = db_name.replace(":", "-")
    return os.path.join(database_dir, db_name)

def get_all_databases() -> List[str]:
    """获取所有知识库名称"""
    if not os.path.exists(database_dir):
        return []
    return [d for d in os.listdir(database_dir) if os.path.isdir(os.path.join(database_dir, d))]

def delete_database(db_name: str) -> bool:
    """删除知识库"""
    db_path = get_persist_directory(db_name)
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
        return True
    return False

def save_uploaded_file(file, filename: str) -> str:
    """保存上传的文件到documents目录"""
    file_path = os.path.join(documents_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(file.read())
    return file_path

def create_db(model_name: str, db_name: str, file_paths: List[str] = None, vector_db: Optional[VectorDB] = None) -> VectorDB:
    """创建向量数据库
    
    Args:
        model_name: 嵌入模型名称
        db_name: 数据库名称
        file_paths: 要嵌入的文件路径列表
        vector_db: 可选的向量数据库实例
    
    Returns:
        VectorDB: 向量数据库实例
    """
    persist_directory = get_persist_directory(db_name)
    
    if vector_db is None:
        vector_db = LocalVectorDBChroma(
            model_name=model_name,
            persist_directory=persist_directory
        )
    
    # 如果提供了文件路径，则嵌入这些文件
    if file_paths and not os.path.exists(persist_directory):
        for file_path in file_paths:
            if file_path.endswith('.csv'):
                vector_db.embed_csv(file_path)
            elif file_path.endswith('.json'):
                vector_db.embed_json(file_path)
            elif file_path.endswith('.txt'):
                vector_db.embed_txt(file_path)
            elif file_path.startswith('http'):
                vector_db.embed_webpage(file_path)
        
    return vector_db

def ask_agent(
    embed_model_name: str,
    chat_model_name: str,
    query: str,
    db_name: str,
    use_api: bool = False,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    vector_db: Optional[VectorDB] = None,
    callback = None  # 添加回调函数参数
):
    """运行RAG智能体"""
    vector_db = vector_db or create_db(embed_model_name, db_name)
    
    # 创建检索器
    vector_store = vector_db.get_vector_store()
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 2}
    )
    
    # 创建工具
    tools = [
        retriever.as_tool(
            name="info_retriever",
            description="查询信息"
        )
    ]
    
    # 创建LLM
    llm = (ChatOpenAI(
            model=chat_model_name,
            temperature=0.1,
            verbose=True,
            api_key=api_key,
            base_url=api_base
        ) if use_api else ChatOllama(
            model=chat_model_name,
            temperature=0.1,
            verbose=True
        ))
    
    # 创建智能体
    agent = create_react_agent(llm, tools)
    
    # 运行智能体
    for chunk in agent.stream({"messages": [("human", query)]}):
        # 如果提供了回调函数，调用它
        if callback:
            callback(chunk)
            
        if "agent" in chunk:
            agent_message = chunk["agent"]["messages"][0]
            if agent_message.tool_calls:
                tool_call = agent_message.tool_calls[0]
                print(f"🔍 正在查询: {tool_call['args'].get('__arg1', '')}")
            elif agent_message.content:
                print(f"\n🤖 回答:\n{agent_message.content}\n")
        elif "tools" in chunk:
            tool_message = chunk["tools"]["messages"][0]
            print(f"📚 找到相关信息:")
            try:
                import re
                content = tool_message.content
                docs = re.findall(r"page_content='(.*?)'", content)
                for doc in docs:
                    formatted_doc = doc.replace("\\n", "\n  ")
                    print(f"  {formatted_doc}")
            except:
                print(f"  {tool_message.content}")

def test_model(
    embed_model_name: str,
    chat_model_name: str,
    db_name: str = "test_db",
    use_api: bool = False,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None
):
    """测试模型"""
    print(f'\n---------------------{embed_model_name}-----------------------------')
    # 使用默认的animals_custom.csv文件创建测试数据库
    src_file_path = os.path.join(documents_dir, 'animals_custom.csv')
    create_db(embed_model_name, db_name, [src_file_path])
    
    queries = [
        "羊的学名是什么？它对人类有什么用处？",
        "猪的特点是什么？它对人类社会有什么作用？"
    ]
    
    for query in queries:
        ask_agent(embed_model_name, chat_model_name, query, db_name, use_api, api_key, api_base)

if __name__ == '__main__':
    test_model("llama3.1", "qwen-turbo", "animals_db", use_api=True, api_key=openai_api_key, api_base=openai_api_base)