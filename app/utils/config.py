"""
配置管理模块
管理应用的配置信息和环境变量
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def setup_logging():
    """配置应用日志"""
    # 检查是否启用了服务端日志文件
    log_to_file = os.getenv("LOG_TO_FILE", "false").lower() == "true"
    log_level_str = os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str)
    log_dir = Path(os.getenv("LOG_DIR", "logs"))

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 创建格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（可选）
    if log_to_file:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"georag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        print(f"📝 服务端日志将写入文件: {log_file}")

    # 配置第三方库的日志级别
    third_party_loggers = {
        "httpx": log_level,
        "httpcore": log_level,
        "mcp.client": log_level,
        "mcp.client.streamable_http": log_level,
        "langgraph": log_level,
        "langchain": log_level,
        "watchfiles": log_level,
        "uvicorn": log_level,
    }

    for logger_name, level in third_party_loggers.items():
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.setLevel(level)


# 配置日志
setup_logging()


class AppConfig:
    """应用配置类"""

    # 应用基本信息
    APP_NAME = "GeoAgent API"
    VERSION = "1.0.0"
    DESCRIPTION = "GeoAgent API Documentation with Swagger"

    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 7512

    # CORS配置
    CORS_ORIGINS = ["*"]
    CORS_METHODS = ["*"]
    CORS_HEADERS = ["*"]

    # API配置
    API_PREFIX = "/llm/v1"
    REDOC_URL = None
    MCP_AGENT_TIMEOUT_SECONDS = float(os.getenv("MCP_AGENT_TIMEOUT_SECONDS", "300"))

    # 响应状态码
    SUCCESS_CODE = 2000
    ERROR_CODE = 5000

    # MCP server configuration — full config loaded from env as JSON.
    # Format: '{"server_name": {"url": "...", "transport": "streamable_http"}, ...}'
    MCP_CONFIG: dict = json.loads(os.getenv("MCP_CONFIG", "{}"))


# 全局配置实例
config = AppConfig()
