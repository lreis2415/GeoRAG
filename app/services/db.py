# app/db.py
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL is not set in environment variables")

# 创建 Engine
engine = create_engine(DB_URL, echo=False, future=True)

# 创建 Session 工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base 供 ORM 模型继承（后面如果要加 ORM）
Base = declarative_base()
