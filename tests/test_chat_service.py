"""
Tests for chat_service.py
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.services.chat_service import ChatService
from app.utils.config import config

# 添加 patch 到导入，以便在测试中使用

# ==================== Fixtures ====================


@pytest.fixture
def mock_db():
    """Mock 数据库会话"""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_dao():
    """Mock ChatDAO"""
    dao = MagicMock()
    dao.save_session = MagicMock()
    dao.get_session_history = MagicMock(return_value=[])
    dao.delete_session = MagicMock(return_value=True)
    dao.clear_all_sessions = MagicMock()
    dao.get_all_sessions = MagicMock(return_value=[])
    dao.get_session = MagicMock(return_value=None)
    dao.update_session_title = MagicMock(return_value=True)
    return dao


@pytest.fixture
def mock_database_service():
    """Mock DatabaseService"""
    db_service = MagicMock()
    db_service.get_vector_db = MagicMock(return_value=None)
    return db_service


@pytest.fixture
def service(mock_dao, mock_db):
    """创建 ChatService 实例"""
    service = ChatService(db_session=mock_db, database_service=None)
    service.dao = mock_dao
    return service


@pytest.fixture
def service_with_db(mock_dao, mock_db, mock_database_service):
    """创建带 DatabaseService 的 ChatService 实例"""
    service = ChatService(db_session=mock_db, database_service=mock_database_service)
    service.dao = mock_dao
    return service


@pytest.fixture
def mock_vector_db():
    """Mock 向量数据库"""
    vector_db = MagicMock()
    vector_store = MagicMock()
    retriever = MagicMock()
    tool = MagicMock()
    tool.name = "info_retriever"

    retriever.as_tool.return_value = tool
    vector_store.as_retriever.return_value = retriever
    vector_db.get_vector_store.return_value = vector_store
    return vector_db


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    llm = MagicMock()
    response = MagicMock()
    response.content = "这是AI的回复"
    llm.ainvoke = AsyncMock(return_value=response)
    return llm


@pytest.fixture
def mock_agent():
    """Mock Agent"""
    agent = MagicMock()
    result = MagicMock()
    message = MagicMock()
    message.content = "这是Agent的回复"
    result["messages"] = [message]
    agent.ainvoke = AsyncMock(return_value=result)
    return agent


# ==================== 测试创建会话 ====================


def test_create_session_with_new_id(service, mock_dao, mock_db):
    """测试创建新会话（自动生成ID）"""
    session_id = service.create_session(db=mock_db)

    assert session_id is not None
    assert session_id in service.chat_sessions
    assert "memory" in service.chat_sessions[session_id]
    assert "created_at" in service.chat_sessions[session_id]
    assert "last_active" in service.chat_sessions[session_id]
    assert service.chat_sessions[session_id]["message_count"] == 0
    mock_dao.save_session.assert_called_once_with(mock_db, session_id, title=None)


def test_create_session_with_existing_id(service, mock_db):
    """测试使用已有会话ID"""
    session_id = "test-session-123"
    result = service.create_session(session_id=session_id, db=mock_db)

    assert result == session_id
    assert session_id in service.chat_sessions


def test_create_session_reuses_existing(service, mock_db):
    """测试重复调用create_session使用同一会话"""
    session_id = "test-session-456"

    service.create_session(session_id=session_id, db=mock_db)
    first_session = service.chat_sessions[session_id]

    service.create_session(session_id=session_id, db=mock_db)
    second_session = service.chat_sessions[session_id]

    assert first_session is second_session


def test_create_session_cleanup_when_limit_reached(service, mock_db):
    """测试达到会话数量限制时清理旧会话"""
    # 设置较小的限制用于测试
    service.max_sessions = 3

    # 创建3个会话
    session1 = service.create_session(db=mock_db)
    service.create_session(db=mock_db)
    service.create_session(db=mock_db)

    assert len(service.chat_sessions) == 3

    # 创建第4个会话，应该触发清理
    service.create_session(db=mock_db)

    # 验证旧会话被清理
    assert session1 not in service.chat_sessions
    assert len(service.chat_sessions) <= 3


def test_create_session_db_error_handling(service, mock_dao, mock_db):
    """测试数据库保存失败时的错误处理"""
    mock_dao.save_session.side_effect = Exception("Database error")

    # 不应该抛出异常，应该记录错误
    session_id = service.create_session(db=mock_db)

    assert session_id is not None
    assert session_id in service.chat_sessions


# ==================== 测试清理旧会话 ====================


def test_cleanup_old_sessions(service):
    """测试清理旧会话功能"""
    # 创建多个会话
    old_session = "old-session"
    new_session = "new-session"

    service.chat_sessions[old_session] = {
        "memory": MagicMock(),
        "created_at": datetime(2024, 1, 1),
        "last_active": datetime(2024, 1, 1),
        "message_count": 5,
    }
    service.chat_sessions[new_session] = {
        "memory": MagicMock(),
        "created_at": datetime(2024, 12, 25),
        "last_active": datetime(2024, 12, 25),
        "message_count": 1,
    }

    service._cleanup_old_sessions()

    # 旧会话应该被清理
    assert old_session not in service.chat_sessions


def test_cleanup_old_sessions_empty(service):
    """测试没有会话时的清理"""
    service.chat_sessions = {}
    # 不应该抛出异常
    service._cleanup_old_sessions()
    assert len(service.chat_sessions) == 0


# ==================== 测试更新会话活跃时间 ====================


def test_update_session_activity(service):
    """测试更新会话活跃时间"""
    session_id = "test-session"
    old_time = datetime(2024, 1, 1)

    service.chat_sessions[session_id] = {
        "memory": MagicMock(),
        "created_at": old_time,
        "last_active": old_time,
        "message_count": 0,
    }

    service.update_session_activity(session_id)

    # 最后活跃时间应该被更新
    assert service.chat_sessions[session_id]["last_active"] > old_time


def test_update_session_activity_nonexistent(service):
    """测试更新不存在的会话（应该不报错）"""
    # 不应该抛出异常
    service.update_session_activity("nonexistent-session")


# ==================== 测试添加对话到记忆 ====================


def test_add_to_memory(service, mock_db):
    """测试添加对话到记忆"""
    session_id = "test-session"
    service.create_session(session_id=session_id, db=mock_db)

    service.add_to_memory(
        session_id=session_id,
        human_message="你好",
        ai_message="你好！有什么可以帮助你的？",
        db=mock_db,
    )

    session = service.chat_sessions[session_id]
    assert session["message_count"] == 1
    # 验证消息被添加到记忆
    assert len(session["memory"].chat_memory.messages) == 2


def test_add_to_memory_creates_session_if_not_exists(service, mock_db, mock_dao):
    """测试添加到不存在会话时自动创建"""
    session_id = "new-session"
    mock_dao.get_session_history.return_value = []

    service.add_to_memory(
        session_id=session_id,
        human_message="测试",
        ai_message="回复",
        db=mock_db,
    )

    assert session_id in service.chat_sessions


def test_add_to_memory_exceeds_limit(service, mock_db):
    """测试消息数量超过限制时的清理"""
    session_id = "test-session"
    service.create_session(session_id=session_id, db=mock_db)
    service.max_memory_length = 5

    # 添加超过限制的消息
    for i in range(6):
        service.add_to_memory(
            session_id=session_id,
            human_message=f"消息{i}",
            ai_message=f"回复{i}",
            db=mock_db,
        )

    session = service.chat_sessions[session_id]
    # 消息数量应该被限制
    assert session["message_count"] <= service.max_memory_length


# ==================== 测试获取会话历史 ====================


def test_get_conversation_history(service, mock_dao, mock_db):
    """测试获取会话历史"""
    mock_dao.get_session_history.return_value = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ]

    history = service.get_conversation_history("test-session", db=mock_db)

    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert history[0].content == "你好"
    assert isinstance(history[1], AIMessage)
    assert history[1].content == "你好！"


def test_get_conversation_history_with_system_message(service, mock_dao, mock_db):
    """测试包含系统消息的历史"""
    mock_dao.get_session_history.return_value = [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "你好"},
    ]

    history = service.get_conversation_history("test-session", db=mock_db)

    assert len(history) == 2
    assert isinstance(history[0], SystemMessage)
    assert isinstance(history[1], HumanMessage)


def test_get_conversation_history_empty(service, mock_dao, mock_db):
    """测试空历史记录"""
    mock_dao.get_session_history.return_value = []

    history = service.get_conversation_history("test-session", db=mock_db)

    assert history == []


def test_get_conversation_history_error_handling(service, mock_dao, mock_db):
    """测试数据库错误时的处理"""
    mock_dao.get_session_history.side_effect = Exception("DB error")

    history = service.get_conversation_history("test-session", db=mock_db)

    # 应该返回空列表而不是抛出异常
    assert history == []


# ==================== 测试删除会话 ====================


def test_delete_chat_session_success(service, mock_dao, mock_db):
    """测试成功删除会话"""
    session_id = "test-session"
    service.create_session(session_id=session_id, db=mock_db)

    result = service.delete_chat_session(session_id, db=mock_db)

    assert result is True
    mock_dao.delete_session.assert_called_once_with(mock_db, session_id)


def test_delete_chat_session_not_found(service, mock_dao, mock_db):
    """测试删除不存在的会话"""
    mock_dao.delete_session.return_value = False

    result = service.delete_chat_session("nonexistent", db=mock_db)

    assert result is False


def test_delete_chat_session_db_error(service, mock_dao, mock_db):
    """测试数据库错误时的处理"""
    mock_dao.delete_session.side_effect = Exception("DB error")

    result = service.delete_chat_session("test-session", db=mock_db)

    assert result is False


# ==================== 测试清空所有会话 ====================


def test_clear_all_sessions(service, mock_dao, mock_db):
    """测试清空所有会话"""
    # 创建一些会话
    service.create_session(db=mock_db)
    service.create_session(db=mock_db)

    service.clear_all_sessions(db=mock_db)

    mock_dao.clear_all_sessions.assert_called_once_with(mock_db)


# ==================== 测试获取格式化的历史记录 ====================


def test_get_chat_history_success(service, mock_dao, mock_db):
    """测试成功获取格式化的历史记录"""
    session_id = "test-session"
    mock_dao.get_session_history.return_value = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ]
    mock_dao.get_all_sessions.return_value = [
        {"session_id": session_id, "created_at": "2024-01-01T00:00:00"}
    ]

    result = service.get_chat_history(session_id, db=mock_db)

    assert result["session_id"] == session_id
    assert result["message_count"] == 2
    assert len(result["history"]) == 2
    assert result["history"][0] == {"role": "user", "content": "你好"}
    assert result["history"][1] == {"role": "assistant", "content": "你好！"}
    assert "created_at" in result
    assert "last_active" in result


def test_get_chat_history_missing_session_id(service, mock_db):
    """测试缺少 session_id 参数"""
    with pytest.raises(ValueError) as exc_info:
        service.get_chat_history("", db=mock_db)
    assert str(exc_info.value) == "session_id is required"

    with pytest.raises(ValueError) as exc_info:
        service.get_chat_history(None, db=mock_db)
    assert str(exc_info.value) == "session_id is required"


def test_get_chat_history_session_not_found(service, mock_dao, mock_db):
    """测试获取不存在的会话"""
    mock_dao.get_session_history.return_value = []
    mock_dao.get_all_sessions.return_value = []

    with pytest.raises(ValueError) as exc_info:
        service.get_chat_history("nonexistent", db=mock_db)
    assert str(exc_info.value) == "Session not found"


def test_get_chat_history_from_memory(service, mock_dao, mock_db):
    """测试从内存获取历史记录"""
    session_id = "test-session"
    # Mock session_exists 返回 True
    mock_dao.get_all_sessions.return_value = [
        {"session_id": session_id, "created_at": "2024-01-01T00:00:00"}
    ]
    service.create_session(session_id=session_id, db=mock_db)
    service.add_to_memory(session_id, "你好", "你好！", db=mock_db)

    result = service.get_chat_history(session_id, db=mock_db)

    assert result["message_count"] == 0  # 数据库历史为空
    assert "history" in result


# ==================== 测试检查会话是否存在 ====================


def test_session_exists_true(service, mock_dao, mock_db):
    """测试会话存在的情况"""
    mock_dao.get_all_sessions.return_value = [
        {"session_id": "test-session"},
        {"session_id": "other-session"},
    ]

    result = service.session_exists("test-session", db=mock_db)

    assert result is True


def test_session_exists_false(service, mock_dao, mock_db):
    """测试会话不存在的情况"""
    mock_dao.get_all_sessions.return_value = [
        {"session_id": "other-session"},
    ]

    result = service.session_exists("nonexistent", db=mock_db)

    assert result is False


def test_session_exists_db_error(service, mock_dao, mock_db):
    """测试数据库错误时的处理"""
    mock_dao.get_all_sessions.side_effect = Exception("DB error")

    result = service.session_exists("test-session", db=mock_db)

    # 应该返回 False 而不是抛出异常
    assert result is False


def test_session_exists_empty_list(service, mock_dao, mock_db):
    """测试空会话列表"""
    mock_dao.get_all_sessions.return_value = []

    result = service.session_exists("test-session", db=mock_db)

    assert result is False


# ==================== 测试会话标题生成 ====================


def test_generate_session_title_normal(service):
    """测试正常标题生成"""
    title = service.generate_session_title("请帮我总结一下这篇论文的核心观点")
    assert title == "请帮我总结一下这篇论文的核心观点"


def test_generate_session_title_empty(service):
    """测试空输入时回退默认标题"""
    assert service.generate_session_title("") == "New Chat"
    assert service.generate_session_title("   ") == "New Chat"


def test_generate_session_title_with_newline_and_trim(service):
    """测试换行归一化和长度截断"""
    long_query = "这是第一行\n这是第二行\n这是第三行并且非常非常长需要被截断"
    title = service.generate_session_title(long_query)
    assert "\n" not in title
    assert len(title) <= service.max_session_title_length


def test_ensure_session_title_when_missing(service, mock_dao, mock_db):
    """测试缺失标题时自动设置"""
    mock_dao.get_session.return_value = {
        "session_id": "s1",
        "title": None,
        "created_at": "2024-01-01T00:00:00",
    }

    title = service.ensure_session_title("s1", "你好，帮我写周报", db=mock_db)

    assert title == "你好，帮我写周报"
    mock_dao.update_session_title.assert_called_once_with(mock_db, "s1", title)


def test_ensure_session_title_when_exists(service, mock_dao, mock_db):
    """测试已有标题时不重复更新"""
    mock_dao.get_session.return_value = {
        "session_id": "s1",
        "title": "已有标题",
        "created_at": "2024-01-01T00:00:00",
    }

    title = service.ensure_session_title("s1", "新的问题", db=mock_db)

    assert title == "已有标题"
    mock_dao.update_session_title.assert_not_called()


# ==================== 测试 chat_with_agent ====================


@pytest.mark.asyncio
async def test_chat_with_agent_no_tools_no_memory(service, mock_llm):
    """测试纯对话模式（不使用工具，不使用记忆）"""
    with patch.object(service, "_create_llm", return_value=mock_llm):
        result = await service.chat_with_agent(
            prompt="你是一个友好的助手",
            query="你好",
            use_memory=False,
        )

        assert result["response"] == "这是AI的回复"
        mock_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_chat_with_agent_with_memory(service, mock_llm, mock_dao, mock_db):
    """测试对话 + 记忆模式"""
    history = [
        HumanMessage(content="你好"),
        AIMessage(content="你好！"),
    ]

    with patch.object(service, "_create_llm", return_value=mock_llm):
        result = await service.chat_with_agent(
            prompt="你是一个友好的助手",
            query="我叫小明",
            use_memory=True,
            history=history,
        )

        assert result["response"] == "这是AI的回复"


@pytest.mark.asyncio
async def test_chat_with_agent_with_rag(
    service_with_db, mock_llm, mock_vector_db, mock_database_service
):
    """测试对话 + RAG 模式"""
    mock_database_service.get_vector_db.return_value = mock_vector_db

    with patch.object(service_with_db, "_create_llm", return_value=mock_llm):
        result = await service_with_db.chat_with_agent(
            prompt="你是一个地理专家",
            query="什么是数字地形模型？",
            db_name="geo_knowledge",
            use_memory=False,
        )

        assert result["response"] == "这是AI的回复"
        mock_database_service.get_vector_db.assert_called_once_with("geo_knowledge")


@pytest.mark.asyncio
async def test_chat_with_agent_with_mcp_tools(service, mock_agent):
    """测试对话 + MCP 工具模式"""
    mcp_tools = [MagicMock(name="calculator")]

    with patch("app.services.chat_service.create_react_agent", return_value=mock_agent):
        with patch.object(service, "_create_llm"):
            result = await service.chat_with_agent(
                prompt="你是一个助手",
                query="帮我计算 2+2",
                mcp_tools=mcp_tools,
                use_memory=False,
            )

            assert result["response"] == "这是Agent的回复"


@pytest.mark.asyncio
async def test_chat_with_agent_passes_configured_recursion_limit(service):
    """非流式 Agent 应将配置的 LangGraph 递归预算传入 ainvoke。"""
    agent = MagicMock()
    agent.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="这是Agent的回复")]}
    )

    with patch("app.services.chat_service.create_react_agent", return_value=agent):
        with patch.object(service, "_create_llm"):
            result = await service.chat_with_agent(
                prompt="你是一个助手",
                query="调用工具后回答",
                mcp_tools=[MagicMock(name="calculator")],
                use_memory=False,
            )

    assert result["response"] == "这是Agent的回复"
    invoke_config = agent.ainvoke.call_args.kwargs["config"]
    assert invoke_config["recursion_limit"] == config.MCP_AGENT_RECURSION_LIMIT


@pytest.mark.asyncio
async def test_chat_stream_passes_configured_recursion_limit(service):
    """流式 Agent 应将配置的 LangGraph 递归预算传入 astream。"""
    agent = MagicMock()

    async def empty_stream(*_args, **_kwargs):
        if False:
            yield None

    agent.astream = MagicMock(return_value=empty_stream())

    with patch("app.services.chat_service.create_react_agent", return_value=agent):
        with patch.object(service, "_create_llm"):
            events = [
                event
                async for event in service.chat_stream(
                    prompt="你是一个助手",
                    query="调用工具后回答",
                    mcp_tools=[MagicMock(name="calculator")],
                    use_memory=False,
                )
            ]

    assert events == []
    stream_config = agent.astream.call_args.kwargs["config"]
    assert stream_config["recursion_limit"] == config.MCP_AGENT_RECURSION_LIMIT


@pytest.mark.asyncio
async def test_chat_with_agent_with_rag_and_tools(
    service_with_db, mock_agent, mock_vector_db, mock_database_service
):
    """测试对话 + RAG + MCP 工具模式"""
    mock_database_service.get_vector_db.return_value = mock_vector_db
    mcp_tools = [MagicMock(name="calculator")]

    with patch("app.services.chat_service.create_react_agent", return_value=mock_agent):
        with patch.object(service_with_db, "_create_llm"):
            result = await service_with_db.chat_with_agent(
                prompt="你是一个地理专家",
                query="请分析地形数据",
                db_name="geo_knowledge",
                mcp_tools=mcp_tools,
                use_memory=False,
            )

            assert result["response"] == "这是Agent的回复"


@pytest.mark.asyncio
async def test_chat_with_agent_db_not_found(service_with_db, mock_database_service):
    """测试知识库不存在的情况"""
    mock_database_service.get_vector_db.return_value = None

    with pytest.raises(ValueError) as exc_info:
        await service_with_db.chat_with_agent(
            prompt="你是一个助手",
            query="你好",
            db_name="nonexistent_db",
            use_memory=False,
        )

    assert "Knowledge base 'nonexistent_db' not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chat_with_agent_db_service_not_initialized(service):
    """测试 DatabaseService 未初始化的情况"""
    # 创建一个没有 DatabaseService 的实例
    service_no_db = ChatService(db_session=None, database_service=None)

    with pytest.raises(ValueError) as exc_info:
        await service_no_db.chat_with_agent(
            prompt="你是一个助手",
            query="你好",
            db_name="some_db",
            use_memory=False,
        )

    assert "DatabaseService is not initialized" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chat_with_agent_missing_prompt(service):
    """测试缺少 prompt 参数"""
    with pytest.raises(ValueError) as exc_info:
        await service.chat_with_agent(
            prompt="",
            query="你好",
            use_memory=False,
        )

    assert str(exc_info.value) == "prompt is required"


@pytest.mark.asyncio
async def test_chat_with_agent_missing_query(service):
    """测试缺少 query 参数"""
    with pytest.raises(ValueError) as exc_info:
        await service.chat_with_agent(
            prompt="你是一个助手",
            query="",
            use_memory=False,
        )

    assert str(exc_info.value) == "query is required"


@pytest.mark.asyncio
async def test_chat_with_agent_with_session_id(service, mock_llm):
    """测试带 session_id 的对话"""
    with patch.object(service, "_create_llm", return_value=mock_llm):
        result = await service.chat_with_agent(
            prompt="你是一个助手",
            query="你好",
            session_id="test-session-123",
            use_memory=False,
        )

        assert result["response"] == "这是AI的回复"
        assert result["session_id"] == "test-session-123"


# ==================== 测试 _create_llm ====================


def test_create_llm_with_default_model(service):
    """测试使用默认模型创建 LLM"""
    with patch("app.services.chat_service.ChatOpenAI") as mock_chat_openai:
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance

        result = service._create_llm()

        mock_chat_openai.assert_called_once()
        assert result == mock_llm_instance


def test_create_llm_with_custom_model(service):
    """测试使用自定义模型创建 LLM"""
    with patch("app.services.chat_service.ChatOpenAI") as mock_chat_openai:
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance

        result = service._create_llm("qwen-plus-2025-07-28")

        mock_chat_openai.assert_called_once_with(
            model="qwen-plus-2025-07-28",
            temperature=0.1,
            verbose=True,
            api_key=mock_chat_openai.call_args[1]["api_key"],  # 从环境变量获取
            base_url=mock_chat_openai.call_args[1]["base_url"],  # 从环境变量获取
        )
        assert result == mock_llm_instance
