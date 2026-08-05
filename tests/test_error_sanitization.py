"""
错误清洗模块测试

验证 `app/utils/errors.py::safe_error_message` 能正确分类常见供应商错误，
并确保返回消息不包含原始错误体的敏感细节（id / request_id / 内部 JSON）。
同时验证 chat 接口在底层模型调用失败时返回脱敏消息。
"""

from unittest.mock import MagicMock

import pytest

from app.auth.dependencies import CurrentUser
from app.routers.chat import chat_with_agent
from app.utils.errors import safe_error_message
from app.utils.models import ChatRequest

# 用户反馈的真实欠费错误（火山方舟 403 FreeTierOnly）
QUOTA_EXHAUSTED_ERROR = (
    "Error code: 403 - {'error': {'message': 'Free quota exhausted. To continue "
    "accessing the model on a paid basis, please add funds or disable the "
    "\\\"use free tier only\\\" mode in the management console.', 'type': "
    "'AllocationQuota.FreeTierOnly', 'param': None, 'code': "
    "'AllocationQuota.FreeTierOnly'}, 'id': "
    "'chatcmpl-e5d52646-8875-9615-809c-0668d2589c5c', 'request_id': "
    "'e5d52646-8875-9615-809c-0668d2589c5c'}"
)

QUOTA_MESSAGE = (
    "Model quota exhausted or account balance insufficient. Please top up your account "
    "or contact the administrator."
)
AUTH_MESSAGE = (
    "Model service authentication failed. Please check your API key configuration."
)
RATE_LIMIT_MESSAGE = "Model request rate limit exceeded. Please try again later."
MODEL_NOT_FOUND_MESSAGE = "The requested model does not exist or is unavailable."
TIMEOUT_MESSAGE = "Model call timed out. Please try again later."


# ==================== safe_error_message 分类测试 ====================


class TestSafeErrorMessage:
    def test_quota_exhausted_full_sdk_error(self):
        """用户反馈的完整欠费错误应映射为额度不足消息，且不含敏感信息"""
        message = safe_error_message(Exception(QUOTA_EXHAUSTED_ERROR))
        assert message == QUOTA_MESSAGE
        assert "chatcmpl" not in message
        assert "request_id" not in message
        assert "Free quota" not in message
        assert "AllocationQuota" not in message

    def test_quota_insufficient_balance(self):
        """Insufficient Balance 应归类为额度不足"""
        message = safe_error_message(
            Exception("Error code: 402 - Insufficient Balance for this account")
        )
        assert message == QUOTA_MESSAGE

    def test_quota_free_tier_keyword(self):
        """Free tier / quota 关键词应归类为额度不足"""
        message = safe_error_message(
            Exception("Free tier quota exhausted for model qwen-turbo-latest")
        )
        assert message == QUOTA_MESSAGE

    def test_auth_invalid_api_key(self):
        """无效 API Key 应归类为认证失败"""
        message = safe_error_message(
            Exception("Error code: 401 - Invalid API key provided")
        )
        assert message == AUTH_MESSAGE

    def test_rate_limit(self):
        """限流应归类为过于频繁"""
        message = safe_error_message(
            Exception("Error code: 429 - Rate limit reached, retry after 30s")
        )
        assert message == RATE_LIMIT_MESSAGE

    def test_model_not_found(self):
        """模型不存在应归类为模型不可用"""
        message = safe_error_message(
            Exception("Error code: 404 - Model not found: qwen-turbo-latest")
        )
        assert message == MODEL_NOT_FOUND_MESSAGE

    def test_timeout(self):
        """超时应归类为超时提示"""
        message = safe_error_message(Exception("Request timed out after 30s"))
        assert message == TIMEOUT_MESSAGE

    def test_status_code_fallback(self):
        """无匹配文本但携带 HTTP 状态码时应按状态码兜底分类"""
        exc = Exception("Something went wrong upstream")
        exc.status_code = 403
        message = safe_error_message(exc)
        assert (
            message
            == "Model service access denied. Please check your account quota or "
            "permissions."
        )

    def test_unknown_error_returns_fallback(self):
        """未知错误应返回兜底消息，不泄漏原始内容"""
        message = safe_error_message(
            Exception("internal traceback chatcmpl-xxx request_id=yyy: boom")
        )
        assert message == "Internal server error"
        assert "chatcmpl" not in message
        assert "request_id" not in message

    def test_custom_fallback(self):
        """自定义 fallback 应生效"""
        message = safe_error_message(
            Exception("some weird error"), fallback="Chat request failed"
        )
        assert message == "Chat request failed"

    def test_none_exception(self):
        """None 异常应返回 fallback"""
        assert (
            safe_error_message(None, fallback="Chat request failed")
            == "Chat request failed"
        )

    def test_openai_style_error_object(self):
        """模拟 openai.APIError 对象（含 status_code 属性）"""
        exc = Exception("An error occurred during the request")
        exc.status_code = 401
        assert safe_error_message(exc) == AUTH_MESSAGE


# ==================== chat 接口脱敏测试 ====================


@pytest.mark.asyncio
async def test_chat_endpoint_sanitizes_quota_error(monkeypatch):
    """chat 接口在模型欠费时应返回脱敏消息，code=5010，不泄漏 SDK 错误体"""
    mock_dao = MagicMock()
    monkeypatch.setattr("app.routers.chat.chat_dao", mock_dao)

    mock_chat_service = MagicMock()
    mock_chat_service.chat_with_agent.side_effect = Exception(QUOTA_EXHAUSTED_ERROR)

    mock_model_service = MagicMock()
    mock_model_service.validate_chat_model.return_value = True

    mock_mcp_service = MagicMock()
    mock_mcp_service.is_mcp_initialized.return_value = False

    current_user = CurrentUser(
        user_id="test-user", username="tester", role="TEST", claims={}
    )

    resp = await chat_with_agent(
        request=ChatRequest(
            prompt="你是助手",
            query="你好",
            chat_model_name="qwen-turbo-latest",
            use_memory=False,
        ),
        credentials=None,
        current_user=current_user,
        chat_service=mock_chat_service,
        model_service=mock_model_service,
        mcp_service=mock_mcp_service,
        db=MagicMock(),
    )

    assert resp["success"] is False
    assert resp["code"] == 5010
    assert resp["message"] == QUOTA_MESSAGE
    assert "chatcmpl" not in resp["message"]
    assert "request_id" not in resp["message"]
    # 运行状态应标记为 failed
    mock_dao.finish_chat_run.assert_called_once()
    args = mock_dao.finish_chat_run.call_args
    assert args.args[2] == "failed"


@pytest.mark.asyncio
async def test_chat_endpoint_unknown_error_uses_fallback(monkeypatch):
    """chat 接口遇到未知异常应返回兜底消息而非原始错误"""
    mock_dao = MagicMock()
    monkeypatch.setattr("app.routers.chat.chat_dao", mock_dao)

    mock_chat_service = MagicMock()
    mock_chat_service.chat_with_agent.side_effect = Exception(
        "engine exploded at chatcmpl-xxx with request_id=yyy"
    )

    mock_model_service = MagicMock()
    mock_model_service.validate_chat_model.return_value = True

    mock_mcp_service = MagicMock()
    mock_mcp_service.is_mcp_initialized.return_value = False

    current_user = CurrentUser(
        user_id="test-user", username="tester", role="TEST", claims={}
    )

    resp = await chat_with_agent(
        request=ChatRequest(
            prompt="你是助手",
            query="你好",
            chat_model_name="qwen-turbo-latest",
            use_memory=False,
        ),
        credentials=None,
        current_user=current_user,
        chat_service=mock_chat_service,
        model_service=mock_model_service,
        mcp_service=mock_mcp_service,
        db=MagicMock(),
    )

    assert resp["success"] is False
    assert resp["code"] == 5010
    assert resp["message"] == "Chat request failed"
    assert "chatcmpl" not in resp["message"]


@pytest.mark.asyncio
async def test_chat_endpoint_value_error_preserved(monkeypatch):
    """业务校验类 ValueError 仍应原样返回（如参数错误），code=4000"""
    mock_dao = MagicMock()
    monkeypatch.setattr("app.routers.chat.chat_dao", mock_dao)

    mock_chat_service = MagicMock()
    mock_chat_service.chat_with_agent.side_effect = ValueError("prompt is required")

    mock_model_service = MagicMock()
    mock_model_service.validate_chat_model.return_value = True

    mock_mcp_service = MagicMock()
    mock_mcp_service.is_mcp_initialized.return_value = False

    current_user = CurrentUser(
        user_id="test-user", username="tester", role="TEST", claims={}
    )

    resp = await chat_with_agent(
        request=ChatRequest(
            prompt="你是助手",
            query="你好",
            chat_model_name="qwen-turbo-latest",
            use_memory=False,
        ),
        credentials=None,
        current_user=current_user,
        chat_service=mock_chat_service,
        model_service=mock_model_service,
        mcp_service=mock_mcp_service,
        db=MagicMock(),
    )

    assert resp["success"] is False
    assert resp["code"] == 4000
    assert resp["message"] == "prompt is required"
