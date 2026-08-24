# app/services/db.py
import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base

# 导入 ORM 模型，确保其注册到 Base.metadata（否则 create_all 不会建表）
# noqa: F401 - 导入仅为注册表结构
from app.models import ChatMessage, ChatSession  # noqa: F401

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL is not set in environment variables")

# 创建 Engine
engine = create_engine(DB_URL, echo=False, future=True)

# 自动创建缺失的表（幂等：仅创建不存在的表，不会改动已有表结构）。
# 用于兼容初始化 SQL 只在新数据库卷上执行的情况（如 docker-entrypoint-initdb.d）。
try:
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表结构检查完成（缺失表已自动创建）")
except Exception:
    # 数据库暂时不可用时不影响启动，运行期 ChatDAO 会按需补建
    logger.exception("启动时自动建表失败，将在运行时按需补建")

# 创建 Session 工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
