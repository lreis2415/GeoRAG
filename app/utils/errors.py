"""
错误清洗模块

将底层异常（如 LLM/嵌入供应商 SDK 错误）转换为安全、用户友好的消息，
避免将完整错误体（含 id / request_id / 内部 JSON）泄漏给 API 客户端。

完整原始错误应通过服务端日志（logger.exception 等）记录。
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# 常见供应商错误的识别模式 -> 友好消息（按优先级从高到低）
_ERROR_PATTERNS = [
    # 额度 / 欠费
    (
        r"(free quota exhausted|allocationquota\.freetieronly|insufficient balance|"
        r"insufficient_quota|quota|欠费|balance)",
        "Model quota exhausted or account balance insufficient. Please top up "
        "your account or contact the administrator.",
    ),
    # 认证失败
    (
        r"(invalid api key|authenticationerror|unauthorized|invalid.*key)",
        "Model service authentication failed. Please check your API key configuration.",
    ),
    # 限流
    (
        r"(rate\s*limit|rate_limit|too many requests)",
        "Model request rate limit exceeded. Please try again later.",
    ),
    # 模型不存在
    (
        r"(model not found|model_not_found|no such model)",
        "The requested model does not exist or is unavailable.",
    ),
    # 超时
    (
        r"(timed?\s*out|timeout)",
        "Model call timed out. Please try again later.",
    ),
]

# HTTP 状态码 -> 友好消息（兜底分类）
_STATUS_CODE_MESSAGES = {
    401: (
        "Model service authentication failed. "
        "Please check your API key configuration."
    ),
    403: "Model service access denied. Please check your account quota or permissions.",
    404: "The requested model does not exist or is unavailable.",
    429: "Model request rate limit exceeded. Please try again later.",
}


def _extract_status_code(exc: Exception) -> Optional[int]:
    """从异常中提取 HTTP 状态码（如 openai.APIError.status_code）。"""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and 100 <= value < 600:
            return value
    return None


def safe_error_message(
    exc: Optional[Exception], fallback: str = "Internal server error"
) -> str:
    """
    将异常转换为安全的、用户友好的消息。

    返回值保证不包含原始错误体的敏感细节（id / request_id / 内部 JSON），
    完整原始错误请通过服务端日志记录。

    Args:
        exc: 原始异常，None 时直接返回 fallback
        fallback: 未识别错误时的兜底消息

    Returns:
        脱敏后的用户友好消息
    """
    if not exc:
        return fallback

    message = str(exc)

    # 1. 按文本模式匹配（优先，可处理 SDK 已序列化的错误体）
    for pattern, friendly in _ERROR_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            return friendly

    # 2. 按异常携带的 HTTP 状态码兜底分类
    status_code = _extract_status_code(exc)
    if status_code in _STATUS_CODE_MESSAGES:
        return _STATUS_CODE_MESSAGES[status_code]

    # 3. 兜底
    return fallback
