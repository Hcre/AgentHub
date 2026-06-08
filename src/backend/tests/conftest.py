"""测试夹具：SQLite in-memory + 有效加密密钥，隔离外部依赖。"""

from __future__ import annotations

import base64
import os

# 必须在导入 app.* 之前设置环境变量（settings 启动即读取并缓存）
os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

# 测试必须 hermetic：强制清空所有 LLM 凭据，杜绝真实/计费调用。
# 用 "=" 强制覆盖（os.environ 优先级高于 .env），即使 backend/.env 配了真 key 也不泄漏进测试。
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["COORDINATOR_API_KEY"] = ""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.infrastructure.db.models  # noqa: F401
from app.infrastructure.db.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
