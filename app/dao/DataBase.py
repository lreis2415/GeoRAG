#!/usr/bin/python
# -*- coding:utf-8 -*-
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from .FlexibleVectorDB import FlexibleVectorDB
from .VectorDB import VectorDB

# 加载环境变量
load_dotenv()
openai_api_key = os.environ.get("OPENAI_API_KEY")
openai_api_base = os.environ.get("OPENAI_API_BASE")
embedding_api_url = os.environ.get("EMBEDDING_API_URL")

# 配置路径
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 统一使用 data/ 目录存储数据
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
documents_dir = os.path.join(project_root, "data", "documents")
database_dir = os.path.join(project_root, "data", "database")

# 确保目录存在
os.makedirs(documents_dir, exist_ok=True)
os.makedirs(database_dir, exist_ok=True)


def get_scoped_db_name(user_id: Optional[str], db_name: str) -> str:
    """Return a storage-only collection name scoped to one Java user."""
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", db_name).strip(".") or "default"
    if not user_id:
        return safe_name
    user_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    return f"user_{user_hash}_{safe_name}"


def get_persist_directory(db_name: str, user_id: Optional[str] = None) -> str:
    """获取按用户隔离的向量数据库存储路径"""
    return os.path.join(database_dir, get_scoped_db_name(user_id, db_name))


def get_all_databases(user_id: Optional[str] = None) -> List[Dict]:
    """获取所有知识库详细信息"""
    use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"

    if use_pgvector:
        return _get_all_databases_pgvector(user_id)
    else:
        return _get_all_databases_chromadb(user_id)


def _get_all_databases_pgvector(user_id: Optional[str] = None) -> List[Dict]:
    """从 PostgreSQL 获取所有知识库详细信息"""
    try:
        from sqlalchemy import create_engine, text

        db_url = os.environ.get("DB_URL")
        if not db_url:
            return []

        engine = create_engine(db_url)
        with engine.connect() as conn:
            # 查询 langchain_pg_collection 表，包含元数据和 UUID
            result = conn.execute(
                text(
                    """
                    SELECT
                        c.uuid,
                        c.name,
                        c.cmetadata,
                        c.created_at,
                        COUNT(e.id) as document_count
                    FROM langchain_pg_collection c
                    LEFT JOIN langchain_pg_embedding e ON c.uuid = e.collection_id
                    GROUP BY c.uuid, c.name, c.cmetadata, c.created_at
                    ORDER BY c.name
                """
                )
            )

            databases = []
            for row in result:
                uuid = row[0]
                name = row[1]
                cmetadata = row[2] or {}
                if user_id is not None and cmetadata.get("user_id") != user_id:
                    continue
                created_at_db = row[3]
                document_count = row[4] or 0

                # 向后兼容：如果元数据中不存在某些字段，使用默认值
                # 对于旧知识库，name 可能不存在，使用 db_name 作为后备
                display_name = cmetadata.get("name") if cmetadata.get("name") else name
                # 对于旧知识库，embedding_model_name 可能不存在
                embedding_model = cmetadata.get("embedding_model_name", "unknown")
                # 对于旧知识库，created_at 可能不存在，使用数据库创建时间
                created_at = cmetadata.get("created_at")
                if not created_at and created_at_db:
                    created_at = created_at_db.isoformat()
                elif not created_at:
                    created_at = datetime.now().isoformat()

                # 构建知识库信息
                db_info = {
                    "id": str(uuid),
                    "name": display_name,
                    "embedding_model_name": embedding_model,
                    "document_count": document_count,
                    "created_at": created_at,
                    "description": cmetadata.get("description"),
                }
                databases.append(db_info)
            return databases
    except Exception as e:
        print(f"⚠️ 从数据库获取知识库列表失败: {e}")
        return []


def _get_all_databases_chromadb(user_id: Optional[str] = None) -> List[Dict]:
    """从 ChromaDB 目录获取所有知识库详细信息"""
    if not os.path.exists(database_dir):
        return []

    databases = []
    for db_name in os.listdir(database_dir):
        db_path = os.path.join(database_dir, db_name)
        if not os.path.isdir(db_path):
            continue

        # 读取元数据文件
        metadata_file = os.path.join(db_path, "metadata.json")
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                import json

                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception as e:
                print(f"⚠️ 读取元数据文件失败 {db_name}: {e}")

        if user_id is not None and metadata.get("user_id") != user_id:
            continue

        # 获取目录创建时间作为后备
        stat = os.stat(db_path)
        created_at = metadata.get("created_at")
        if not created_at:
            created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()

        # 向后兼容：如果元数据中没有 name，使用 db_name
        display_name = metadata.get("name") if metadata.get("name") else db_name
        # 向后兼容：如果元数据中没有 embedding_model_name，使用默认值
        embedding_model = metadata.get("embedding_model_name", "unknown")

        # 获取文档数量
        document_count = 0
        try:
            from .FlexibleVectorDB import FlexibleVectorDB

            embedding_api_url = os.environ.get("EMBEDDING_API_URL")
            model_name = metadata.get("embedding_model_name") or os.environ.get(
                "DEFAULT_EMBEDDING_MODEL", "text-embedding-v4"
            )

            if embedding_api_url:
                vector_db = FlexibleVectorDB(
                    embedding_api_url=embedding_api_url,
                    model_name=model_name,
                    persist_directory=db_path,
                )
                document_count = vector_db.get_document_count()
        except Exception as e:
            print(f"⚠️ 获取文档数量失败 {db_name}: {e}")

        db_info = {
            "id": db_name,
            "name": display_name,
            "embedding_model_name": embedding_model,
            "document_count": document_count,
            "created_at": created_at,
            "description": metadata.get("description"),
        }
        databases.append(db_info)

    return databases


def get_database_info(
    db_name: str, user_id: Optional[str] = None
) -> Optional[Dict]:
    """
    获取单个知识库详细信息

    Args:
        db_name: 知识库名称

    Returns:
        知识库信息字典，不存在返回 None
    """
    use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"

    if use_pgvector:
        return _get_database_info_pgvector(db_name, user_id)
    else:
        return _get_database_info_chromadb(db_name, user_id)


def _get_database_info_pgvector(
    db_name: str, user_id: Optional[str] = None
) -> Optional[Dict]:
    """从 PostgreSQL 获取单个知识库详细信息"""
    try:
        from sqlalchemy import create_engine, text

        db_url = os.environ.get("DB_URL")
        if not db_url:
            return None

        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT
                        c.uuid,
                        c.name,
                        c.cmetadata,
                        c.created_at,
                        COUNT(e.id) as document_count
                    FROM langchain_pg_collection c
                    LEFT JOIN langchain_pg_embedding e ON c.uuid = e.collection_id
                    WHERE c.name = :name
                    GROUP BY c.uuid, c.name, c.cmetadata, c.created_at
                """
                ),
                {"name": get_scoped_db_name(user_id, db_name)},
            )
            row = result.fetchone()
            if not row:
                return None

            uuid = row[0]
            name = row[1]
            cmetadata = row[2] or {}
            if user_id is not None and cmetadata.get("user_id") != user_id:
                return None
            created_at_db = row[3]
            document_count = row[4] or 0

            # 向后兼容处理
            display_name = cmetadata.get("name") if cmetadata.get("name") else name
            embedding_model = cmetadata.get("embedding_model_name", "unknown")
            created_at = cmetadata.get("created_at")
            if not created_at and created_at_db:
                created_at = created_at_db.isoformat()
            elif not created_at:
                created_at = datetime.now().isoformat()

            return {
                "id": str(uuid),
                "name": display_name,
                "embedding_model_name": embedding_model,
                "document_count": document_count,
                "created_at": created_at,
                "description": cmetadata.get("description"),
            }
    except Exception as e:
        print(f"⚠️ 获取知识库信息失败: {e}")
        return None


def _get_database_info_chromadb(
    db_name: str, user_id: Optional[str] = None
) -> Optional[Dict]:
    """从 ChromaDB 获取单个知识库详细信息"""
    db_path = get_persist_directory(db_name, user_id)
    if not os.path.exists(db_path):
        return None

    # 读取元数据文件
    metadata_file = os.path.join(db_path, "metadata.json")
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            import json

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"⚠️ 读取元数据文件失败 {db_name}: {e}")

    if user_id is not None and metadata.get("user_id") != user_id:
        return None

    # 获取目录创建时间作为后备
    stat = os.stat(db_path)
    created_at = metadata.get("created_at")
    if not created_at:
        created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()

    # 向后兼容：如果元数据中没有 name，使用 db_name
    display_name = metadata.get("name") if metadata.get("name") else db_name
    # 向后兼容：如果元数据中没有 embedding_model_name，使用默认值
    embedding_model = metadata.get("embedding_model_name", "unknown")

    # 获取文档数量
    document_count = 0
    try:
        from .FlexibleVectorDB import FlexibleVectorDB

        embedding_api_url = os.environ.get("EMBEDDING_API_URL")
        model_name = metadata.get("embedding_model_name") or os.environ.get(
            "DEFAULT_EMBEDDING_MODEL", "text-embedding-v4"
        )

        if embedding_api_url:
            vector_db = FlexibleVectorDB(
                embedding_api_url=embedding_api_url,
                model_name=model_name,
                persist_directory=db_path,
            )
            document_count = vector_db.get_document_count()
    except Exception as e:
        print(f"⚠️ 获取文档数量失败 {db_name}: {e}")

    return {
        "id": db_name,
        "name": display_name,
        "embedding_model_name": embedding_model,
        "document_count": document_count,
        "created_at": created_at,
        "description": metadata.get("description"),
    }


def get_database_files(
    db_name: str, user_id: Optional[str] = None
) -> List[Dict]:
    """
    获取知识库关联的文件列表

    Args:
        db_name: 知识库名称

    Returns:
        文件信息列表
    """
    use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"
    files = []
    if use_pgvector:
        try:
            from sqlalchemy import create_engine, text

            db_url = os.environ.get("DB_URL")
            if db_url:
                engine = create_engine(db_url)
                with engine.connect() as conn:
                    result = conn.execute(
                        text(
                            "SELECT cmetadata FROM langchain_pg_collection "
                            "WHERE name = :name"
                        ),
                        {"name": get_scoped_db_name(user_id, db_name)},
                    )
                    row = result.fetchone()
                    if row and row[0]:
                        metadata = row[0]
                        if user_id is not None and metadata.get("user_id") != user_id:
                            return []
                        files = metadata.get("files", [])
        except Exception as e:
            print(f"⚠️ 获取知识库文件列表失败: {e}")
    else:
        metadata_file = os.path.join(
            get_persist_directory(db_name, user_id), "metadata.json"
        )
        try:
            import json

            with open(metadata_file, "r", encoding="utf-8") as metadata_handle:
                metadata = json.load(metadata_handle)
            if user_id is None or metadata.get("user_id") == user_id:
                files = metadata.get("files", [])
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"⚠️ 获取知识库文件列表失败: {e}")

    # 构建文件信息列表
    file_infos = []
    for filename in files:
        file_path = os.path.join(
            documents_dir,
            hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
            if user_id
            else "legacy",
            filename,
        )
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            file_infos.append(
                {
                    "filename": filename,
                    "file_path": file_path,
                    "file_size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    return file_infos


def delete_database(db_name: str, user_id: Optional[str] = None) -> bool:
    """删除知识库"""
    use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"

    if use_pgvector:
        try:
            from .PgvectorVectorDB import PgvectorVectorDB

            embedding_api_url = os.environ.get("EMBEDDING_API_URL")
            db_url = os.environ.get("DB_URL")
            model_name = os.environ.get("DEFAULT_EMBEDDING_MODEL", "text-embedding-v4")

            vector_db = PgvectorVectorDB(
                connection_string=db_url,
                db_name=get_scoped_db_name(user_id, db_name),
                model_name=model_name,
                embedding_api_url=embedding_api_url,
            )
            vector_db.delete_collection()
            return True
        except Exception as e:
            print(f"⚠️ 删除数据库失败: {e}")
            return False
    else:
        # 删除 ChromaDB 目录
        db_path = get_persist_directory(db_name, user_id)
        if os.path.exists(db_path):
            shutil.rmtree(db_path)
            return True
        return False


def save_uploaded_file(
    file, filename: str, user_id: Optional[str] = None
) -> str:
    """保存上传的文件到documents目录"""
    user_directory = (
        hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
        if user_id
        else "legacy"
    )
    file_directory = os.path.join(documents_dir, user_directory)
    os.makedirs(file_directory, exist_ok=True)
    file_path = os.path.join(file_directory, filename)
    with open(file_path, "wb") as f:
        f.write(file.read())
    return file_path


def create_db(
    model_name: str,
    db_name: str,
    file_paths: List[str] = None,
    vector_db: Optional[VectorDB] = None,
    use_pgvector: Optional[bool] = None,
    user_id: Optional[str] = None,
) -> VectorDB:
    """创建向量数据库

    Args:
        model_name: 嵌入模型名称
        db_name: 数据库名称
        file_paths: 要嵌入的文件路径列表
        vector_db: 可选的向量数据库实例
        use_pgvector: 是否使用 pgvector (默认从环境变量读取)

    Returns:
        VectorDB: 向量数据库实例
    """
    # 验证必要的环境变量
    if not embedding_api_url:
        raise ValueError(
            "未设置 EMBEDDING_API_URL 环境变量，请在 .env 文件中设置该变量"
        )

    # 确定是否使用 pgvector
    if use_pgvector is None:
        use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"

    storage_db_name = get_scoped_db_name(user_id, db_name)
    persist_directory = get_persist_directory(db_name, user_id)

    if vector_db is None:
        try:
            if use_pgvector:
                # 使用 PgvectorVectorDB
                from .PgvectorVectorDB import PgvectorVectorDB

                db_url = os.environ.get("DB_URL")
                if not db_url:
                    raise ValueError("未设置 DB_URL 环境变量")

                vector_db = PgvectorVectorDB(
                    connection_string=db_url,
                    db_name=storage_db_name,
                    model_name=model_name,
                    embedding_api_url=embedding_api_url,
                    user_id=user_id,
                )
            else:
                # 使用 ChromaDB (原有实现)
                vector_db = FlexibleVectorDB(
                    embedding_api_url=embedding_api_url,
                    model_name=model_name,
                    persist_directory=persist_directory,
                    user_id=user_id,
                )
        except Exception as e:
            raise ValueError(f"创建向量数据库失败: {str(e)}")

    # 如果提供了文件路径，则嵌入这些文件
    should_embed = (
        file_paths and not use_pgvector and not os.path.exists(persist_directory)
    )
    if should_embed or (use_pgvector and file_paths):
        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    raise ValueError(f"文件不存在: {file_path}")

                if file_path.endswith(".csv"):
                    vector_db.embed_csv(file_path)
                elif file_path.endswith(".json"):
                    vector_db.embed_json(file_path)
                elif file_path.endswith(".txt"):
                    vector_db.embed_txt(file_path)
                elif file_path.startswith("http"):
                    vector_db.embed_webpage(file_path)
                else:
                    raise ValueError(f"不支持的文件类型: {file_path}")
        except Exception as e:
            raise ValueError(f"嵌入文件失败: {str(e)}")

    # 确保数据库目录存在：即使没有文件，列表接口也能看到该数据库（仅 ChromaDB）
    if not use_pgvector and not os.path.exists(persist_directory):
        os.makedirs(persist_directory, exist_ok=True)

    # 保存元数据
    metadata = {
        "name": db_name,  # 默认使用db_name作为显示名称
        "user_id": user_id,
        "storage_db_name": storage_db_name,
        "embedding_model_name": model_name,
        "created_at": datetime.now().isoformat(),
        "document_count": 0,
        "files": [os.path.basename(fp) for fp in (file_paths or [])],
    }

    try:
        if use_pgvector:
            # 更新 PostgreSQL 中的元数据
            vector_db.update_collection_metadata(metadata)
        else:
            # 保存元数据到文件
            metadata_file = os.path.join(persist_directory, "metadata.json")
            import json

            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存元数据失败: {e}")

    return vector_db


def ask_agent(
    chat_model_name: str,
    query: str,
    use_api: bool = False,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    vector_db: Optional[VectorDB] = None,
    callback=None,  # 添加回调函数参数
    prompt: Optional[str] = None,  # 添加prompt参数
    use_tools: bool = True,
):
    """
    运行RAG智能体

    Args:
        chat_model_name: 聊天模型名称
        query: 用户查询
        use_api: 是否使用API
        api_key: API密钥
        api_base: API基础URL
        vector_db: 向量数据库
        callback: 回调函数
        prompt: 自定义系统提示词
        use_tools: 是否使用RAG工具，默认为True
    """

    # 创建检索器
    vector_store = vector_db.get_vector_store()
    retriever = vector_store.as_retriever(
        search_type="similarity", search_kwargs={"k": 2}
    )
    if use_tools:
        # 创建工具
        tools = [
            retriever.as_tool(
                name="info_retriever",
                description="信息检索工具",
            )
        ]
    else:
        tools = []

    # 创建LLM
    llm = (
        ChatOpenAI(
            model=chat_model_name,
            temperature=0.1,
            verbose=True,
            api_key=api_key,
            base_url=api_base,
            streaming=True,
        )
        if use_api
        else ChatOllama(model=chat_model_name, temperature=0.1, verbose=True)
    )

    # 创建智能体
    agent = create_react_agent(llm, tools)

    # 准备消息
    messages = []

    # 如果提供了自定义提示词，添加系统消息
    if prompt:
        messages.append(("system", prompt))

    # 添加用户查询
    messages.append(("human", query))

    # 运行智能体
    for chunk in agent.stream({"messages": messages}):
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
            print("📚 找到相关信息:")
            try:
                import re

                content = tool_message.content
                docs = re.findall(r"page_content='(.*?)'", content)
                for doc in docs:
                    formatted_doc = doc.replace("\\n", "\n  ")
                    print(f"  {formatted_doc}")
            except Exception:
                print(f"  {tool_message.content}")


def test_model(
    embed_model_name: str,
    chat_model_name: str,
    db_name: str = "test_db",
    use_api: bool = False,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
):
    """测试模型"""
    separator = "-" * 40
    print(f"\n{separator}\n{embed_model_name}\n{separator}")
    # 使用默认的animals_custom.csv文件创建测试数据库
    src_file_path = os.path.join(documents_dir, "animals_custom.csv")
    create_db(embed_model_name, db_name, [src_file_path])

    queries = [
        "羊的学名是什么？它对人类有什么用处？",
        "猪的特点是什么？它对人类社会有什么作用？",
    ]

    for query in queries:
        ask_agent(
            embed_model_name,
            chat_model_name,
            query,
            db_name,
            use_api,
            api_key,
            api_base,
        )


if __name__ == "__main__":
    test_model(
        "llama3.1",
        "qwen-turbo",
        "animals_db",
        use_api=True,
        api_key=openai_api_key,
        api_base=openai_api_base,
    )
