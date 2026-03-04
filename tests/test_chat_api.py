"""
聊天接口测试模块

测试内容包括：
1. GET /v1/chat/init - 初始化会话
2. POST /v1/chat - 聊天对话（使用session_id）

使用方式：
    # 启用日志记录（默认）
    pytest tests/test_chat_api.py -v -s

    # 禁用日志记录
    pytest tests/test_chat_api.py -v -s --no-log
"""

import logging
from datetime import datetime
from pathlib import Path

import pytest
import requests

# ==================== 日志配置 ====================

# 创建 logs 目录（如果不存在）
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志文件路径
log_file = LOG_DIR / f"test_chat_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 创建独立的日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 日志开关（默认启用）
_logging_enabled = True


def enable_logging():
    """启用日志记录"""
    global _logging_enabled
    _logging_enabled = True

    logger.handlers.clear()

    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 防止日志传播到父日志记录器
    logger.propagate = False

    print("✅ 日志记录已启用")
    print(f"   日志文件: {log_file}")


def disable_logging():
    """禁用日志记录"""
    global _logging_enabled
    _logging_enabled = False

    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    print("⚠️  日志记录已禁用")


# 默认启用日志
enable_logging()


# ==================== Pytest 配置 ====================


def pytest_configure(config):
    """Pytest 配置钩子 - 添加命令行选项"""
    config.addinivalue_line("markers", "no_log: 禁用日志记录功能")


@pytest.fixture(scope="session", autouse=True)
def configure_logging(request):
    """根据命令行参数配置日志"""
    # 检查命令行参数
    if request.config.getoption("--no-log"):
        disable_logging()


# ==================== 配置常量 ====================

BASE_URL = "http://0.0.0.0:7512/v1"

# 数字土壤制图专家助手的 Prompt
DIGITAL_SOIL_MAPPING_PROMPT = """你是一位数字土壤制图专家助手，专门负责从自然语言描述中提取结构化的地理建模需求信息，服务于后续建模求解。

## 核心职责

你的任务是分析用户描述，提取出完整的数字土壤制图建模问题所需的结构化信息。建模问题必须包含以下两大类要素，缺一不可：

### 1. 基本信息
- **研究区位置**：具体的地理范围、行政区划或坐标
- **待推测属性**：需要建模的土壤属性（如pH值、有机质含量、土壤质地等）
- **土层深度**：目标土壤剖面层次（如0～20cm）

### 2. 应用场景信息
- **平均坡度**：研究区地理环境特征

## 输出格式

请严格按照以下JSON格式输出结构化结果:
```json
{
  建模问题类型: 数字土壤制图,
  基本信息: {
    研究区位置: 用户描述,
    待推测属性: 具体土壤属性,
    土层: 目标深度范围
  },
  应用场景信息: {
    研究区面积: 数值,
    高程差 (Elevation Difference): 数值,
    标准差 (SDH - Standard Deviation of Height): 数值,
    平均坡度(Mean Slope): 数值,
    空间分辨率 (Resolution): 数值
  }
}
```

## 处理原则

1. 不直接回答用户问题：专注于信息提取和结构化
2. 完整性检查：确保所有必要信息都已包含
3. 缺失信息处理：对于用户未提供但必要的应用场景信息，应该通过工具调用获取真实结果，而不是凭空编造
4. 准确性优先：如有歧义，明确标注并提出澄清建议

## 示例响应框架

- 如果用户提供了完整信息，直接结构化输出
- 如果信息不完整，在JSON的缺失信息处理部分详细说明
"""


# ==================== Pytest Fixtures ====================


@pytest.fixture(scope="session", autouse=True)
def check_service_running():
    """检查 GeoRAG 服务是否运行的 session 级别 fixture"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            pytest.skip("GeoRAG 服务未运行，请先启动服务：python run.py")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pytest.skip("无法连接到 GeoRAG 服务，请确保服务正在运行")


# ==================== 聊天接口测试 ====================


class TestChatAPI:
    """聊天接口测试类"""

    def test_01_chat_init(self):
        """测试初始化会话接口 - GET /v1/chat/init"""
        logger.info("=" * 80)
        logger.info("开始测试: test_01_chat_init - 初始化会话")
        logger.info("=" * 80)

        url = f"{BASE_URL}/chat/init"
        logger.info(f"请求 URL: {url}")
        logger.info("请求方法: GET")

        response = requests.get(url)

        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应头: {dict(response.headers)}")

        # 验证响应状态码
        assert (
            response.status_code == 200
        ), f"Expected status 200, got {response.status_code}"

        # 验证响应结构
        result = response.json()
        logger.info(f"响应体: {result}")

        assert "success" in result, "Response should have 'success' field"
        assert "code" in result, "Response should have 'code' field"
        assert "message" in result, "Response should have 'message' field"
        assert "data" in result, "Response should have 'data' field"

        # 验证响应内容
        assert result["success"] is True, "Response should be successful"
        assert result["code"] == 2000, f"Expected code 2000, got {result['code']}"
        assert (
            result["message"] == "聊天服务已初始化"
        ), f"Unexpected message: {result['message']}"

        # 验证data中包含session_id
        assert (
            "session_id" in result["data"]
        ), "Response data should contain 'session_id'"
        session_id = result["data"]["session_id"]
        assert isinstance(session_id, str), "session_id should be a string"
        assert len(session_id) > 0, "session_id should not be empty"

        # 打印结果供查看
        logger.info("✅ 会话初始化成功")
        logger.info(f"   Session ID: {session_id}")
        print("\n✅ 会话初始化成功")
        print(f"   Session ID: {session_id}")

        # 将session_id保存为类属性，供后续测试使用
        TestChatAPI.session_id = session_id
        logger.info("测试 test_01_chat_init 完成\n")

    def test_02_chat_with_session(self):
        """测试聊天接口 - POST /v1/chat"""
        logger.info("=" * 80)
        logger.info("开始测试: test_02_chat_with_session - 聊天对话")
        logger.info("=" * 80)

        # 确保上一个测试已经执行并获取了session_id
        if not hasattr(TestChatAPI, "session_id"):
            pytest.skip("请先运行 test_01_chat_init 获取 session_id")

        session_id = TestChatAPI.session_id
        logger.info(f"使用 Session ID: {session_id}")

        # 构建聊天请求
        chat_request = {
            "prompt": DIGITAL_SOIL_MAPPING_PROMPT,
            "query": (
                "怎么获取宣城市(50,51,126,127)的SOM分布图？"
                "0～20cm的土层。DEM数据是/Users/wuchenglong/Desktop/EGC/"
                "pygeomodels/data/dem_xc.tif"
            ),
            "chat_model_name": "qwen3-max-preview",
            "session_id": session_id,
            "use_memory": True,
        }

        url = f"{BASE_URL}/chat"
        logger.info(f"请求 URL: {url}")
        logger.info("请求方法: POST")
        logger.info(f"请求体: {chat_request}")

        # 发送聊天请求
        response = requests.post(
            url,
            json=chat_request,
            headers={"Content-Type": "application/json"},
        )

        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应头: {dict(response.headers)}")

        # 验证响应状态码
        assert (
            response.status_code == 200
        ), f"Expected status 200, got {response.status_code}"

        # 验证响应结构
        result = response.json()
        logger.info(f"响应体: {result}")

        assert "success" in result, "Response should have 'success' field"
        assert "code" in result, "Response should have 'code' field"
        assert "data" in result, "Response should have 'data' field"

        # 验证响应内容
        assert result["success"] is True, "Response should be successful"

        # 验证data中包含response字段
        assert "response" in result["data"], "Response data should contain 'response'"
        ai_response = result["data"]["response"]
        assert isinstance(ai_response, str), "AI response should be a string"
        assert len(ai_response) > 0, "AI response should not be empty"

        # 打印结果供查看
        logger.info("✅ 聊天请求成功")
        logger.info(f"   Session ID: {session_id}")
        logger.info(f"   AI Response (完整): {ai_response}")
        logger.info(f"   AI Response (前200字符): {ai_response[:200]}...")
        print("\n✅ 聊天请求成功")
        print(f"   Session ID: {session_id}")
        print(f"   AI Response: {ai_response[:200]}...")  # 只打印前200个字符

        logger.info("测试 test_02_chat_with_session 完成\n")


# ==================== 主函数 ====================


if __name__ == "__main__":
    """可以直接运行此文件进行测试"""
    logger.info("=" * 80)
    logger.info("开始执行测试套件")
    logger.info("=" * 80)
    pytest.main([__file__, "-v", "-s"])
    logger.info("=" * 80)
    logger.info("测试套件执行完毕")
    logger.info("=" * 80)
