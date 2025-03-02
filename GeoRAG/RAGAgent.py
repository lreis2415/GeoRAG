#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
from typing import Optional
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
src_file_path = os.path.join(current_dir, 'documents/animals_custom.csv')

def get_persist_directory(model_name: str) -> str:
    """获取向量数据库存储路径"""
    model_name = model_name.replace(":", "-")
    return os.path.join(current_dir, f'database/animals_{model_name}')

def create_db(model_name: str, vector_db: Optional[VectorDB] = None) -> VectorDB:
    """创建向量数据库"""
    persist_directory = get_persist_directory(model_name)
    
    if vector_db is None:
        vector_db = LocalVectorDBChroma(
            model_name=model_name,
            persist_directory=persist_directory
        )
    
    if not os.path.exists(persist_directory):
        vector_db.embed_csv(src_file_path)
        
    return vector_db

def ask_agent(
    embed_model_name: str,
    chat_model_name: str,
    query: str,
    use_api: bool = False,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    vector_db: Optional[VectorDB] = None
):
    """运行RAG智能体"""
    vector_db = vector_db or create_db(embed_model_name)
    
    # 创建检索器
    vector_store = vector_db.get_vector_store()
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 2}
    )
    
    # 创建工具
    tools = [
        retriever.as_tool(
            name="animals_info_retriever",
            description="查询动物信息"
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
    use_api: bool = False,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None
):
    """测试模型"""
    print(f'\n---------------------{embed_model_name}-----------------------------')
    create_db(embed_model_name)
    
    queries = [
        "羊的学名是什么？它对人类有什么用处？",
        "猪的特点是什么？它对人类社会有什么作用？"
    ]
    
    for query in queries:
        ask_agent(embed_model_name, chat_model_name, query, use_api, api_key, api_base)

if __name__ == '__main__':
    test_model("llama3.1", "qwen-turbo", use_api=True, api_key=openai_api_key, api_base=openai_api_base)