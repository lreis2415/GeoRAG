#!/usr/bin/python
# -*- coding:utf-8 -*-

# https://python.langchain.com/docs/how_to/convert_runnable_to_tool/

"""
1.确定重要文件路径
"""

import os,sys

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# 加载.env文件中的环境变量
load_dotenv()
openai_api_key = os.environ.get("QWEN_API_KEY")
openai_api_base = os.environ.get("QWEN_API_BASE")

# 将上级目录加入path，这样就可以引用上级目录的模块不会报错
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

# 当前文件的绝对路径
current_file_path = os.path.abspath(__file__)

# 当前文件所在的目录
current_dir = os.path.dirname(current_file_path)

# csv源文件地址
src_file_path = os.path.join(current_dir,'documents/animals_custom.csv')
# src_file_path = os.path.join(current_dir,'assert/model_info.csv')
# src_file_path = os.path.join(current_dir,'assert/join-meta-cn.txt')

def get_persist_directory(model_name):
    """矢量数据库存储路径"""
    model_name = model_name.replace(":","-")
    return os.path.join(current_dir,f'database/animals_{model_name}')

"""
2.在本地生成嵌入数据库
"""

from LocalVectorDB import LocalVectorDBChroma
def create_db(model_name):    
    """生成本地矢量数据库"""

    persist_directory = get_persist_directory(model_name)
    if os.path.exists(persist_directory):
        return

    db = LocalVectorDBChroma(model_name,persist_directory)    
    db.embed_csv(src_file_path)
    # db.embed_txt(src_file_path)
    # db.embed_json(src_file_path)
"""
3.智能体
"""

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

def ask_agent(embed_model_name,chat_modal_name,query,use_api=False,api_key=None,api_base=None):
    """测试智能体"""

    persist_directory = get_persist_directory(embed_model_name)
    db = LocalVectorDBChroma(embed_model_name,persist_directory)

    # 基于Chroma 的 vector store 生成 检索器
    vector_store = db.get_vector_store()
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 2},
    )

    # 将 检索器 包装为 工具
    tools = [
        retriever.as_tool(
            name="animals_info_retriever",
            description="查询动物信息",
        )
    ]

    if use_api:
        llm = ChatOpenAI(model=chat_modal_name,temperature=0.1,verbose=True,api_key=api_key,base_url=api_base)
    else:
        llm = ChatOllama(model=chat_modal_name,temperature=0.1,verbose=True)
    agent = create_react_agent(llm, tools)

    # 显示智能体的详细内容
    for chunk in agent.stream({"messages": [("human", query)]}):
        # 处理不同类型的响应
        if "agent" in chunk:
            agent_message = chunk["agent"]["messages"][0]
            
            # 处理工具调用
            if agent_message.tool_calls:
                tool_call = agent_message.tool_calls[0]
                print(f"🔍 正在查询: {tool_call['args'].get('__arg1', '')}")
            # 处理最终回答
            elif agent_message.content:
                print(f"\n🤖 回答:\n{agent_message.content}\n")
        
        # 处理工具返回的结果
        elif "tools" in chunk:
            tool_message = chunk["tools"]["messages"][0]
            print(f"📚 找到相关信息:")
            
            # 尝试提取文档内容并格式化显示
            try:
                import re
                content = tool_message.content
                # 提取文档内容
                docs = re.findall(r"page_content='(.*?)'", content)
                for doc in docs:
                    # 格式化显示文档内容
                    formatted_doc = doc.replace("\\n", "\n  ")
                    print(f"  {formatted_doc}")
            except:
                # 如果解析失败，显示原始内容
                print(f"  {tool_message.content}")

def test_model(embed_model_name,chat_modal_name,use_api=False,api_key=None,api_base=None):
    print(f'\n---------------------{embed_model_name}-----------------------------')
    create_db(embed_model_name)

    query = "羊的学名是什么？它对人类有什么用处？"
    ask_agent(embed_model_name,chat_modal_name,query,use_api,api_key,api_base)

    query = "猪的特点是什么？它对人类社会有什么作用？"
    ask_agent(embed_model_name,chat_modal_name,query,use_api,api_key,api_base)

    # query = "what is the category_application of data_join?"
    # ask_agent(embed_model_name,chat_modal_name,query,use_api,api_key,api_base)

    # query = "what is the description of data_join?"
    # ask_agent(embed_model_name,chat_modal_name,query,use_api,api_key,api_base)

    # query = "what is the organization of data_join?"
    # ask_agent(embed_model_name,chat_modal_name,query,use_api,api_key,api_base)
if __name__ == '__main__':

    # test_model("shaw/dmeta-embedding-zh","qwen2.5")
    # test_model("milkey/m3e","qwen2.5")
    # test_model("mxbai-embed-large","qwen2.5")

    # test_model("nomic-embed-text","llama3.1")
    # test_model("all-minilm:33m","llama3.1")

    # test_model("llama3.1","llama3.1")
    # test_model("qwen2.5","qwen2.5")

    test_model("llama3.1","qwen-turbo",use_api=True,api_key=openai_api_key,api_base=openai_api_base)