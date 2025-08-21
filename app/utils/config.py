"""
配置管理模块
管理应用的配置信息和环境变量
"""

from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)

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
    API_PREFIX = "/llm"
    REDOC_URL = None
    
    # 响应状态码
    SUCCESS_CODE = 2000
    ERROR_CODE = 5000

# 全局配置实例
config = AppConfig()