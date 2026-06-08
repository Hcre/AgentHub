"""t6 /api/usage/global 全平台 Token 聚合 3 路径测试（spec 04-commands §6.6 B-4-P2-T6）。

3 路径（per Task brief）：
1. test_usage_global_1h — 5 条 records 全在 1h 内 → aggregate_global 5 total
2. test_usage_global_top_n — 12 agents → group_by_agent_global 返回 top 10
3. test_usage_global_window_validation — HTTP GET window=invalid → 422

时间旅行策略：直接 UPDATE usage_records.created_at（避免 freezegun）。
HTTP 路径走 FastAPI TestClient，验证 /api/usage/global 端点可达 + 业务校验。
"""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

from fastapi.testclient import TestClient
from sqlalchemy import update

import app.infrastructure.db.models  # noqa: F401
from app.application.services import UsageService
from app.domain.usage import UsageRecord
from app.domain.usage.usage_record import USAGE_KIND_COMPLETION, USAGE_KIND_PROMPT
from app.infrastructure.db.models import UsageRecordModel
from app.infrastructure.repositories import PostgresUsageRepository


async def _seed_records(db_session, *, n: int, hours_ago: float = 0.0) -> None:  # type: ignore[no-untyped-def]
    """往 db_session 直接插 n 条 usage records。"""
    repo = PostgresUsageRepository(db_session)
    for i in range(n):
        await repo.save(
            UsageRecord(
                id=uuid4(),
                agent_id=uuid4(),
                session_id=uuid4(),
                message_id=uuid4(),
                kind=USAGE_KIND_COMPLETION if i % 2 == 0 else USAGE_KIND_PROMPT,
                tokens=10 + i,
                model="mock",
                created_at=datetime.now(UTC) - timedelta(hours=hours_ago),
            )
        )
    await db_session.commit()


async def test_usage_global_1h(db_session) -> None:  # type: ignore[no-untyped-def]
    """5 条 records 全在 1h 内 → aggregate_global 1h window = 60 total。"""
    await _seed_records(db_session, n=5, hours_ago=0.0)
    svc = UsageService(PostgresUsageRepository(db_session))
    result = await svc.aggregate_global(window_name="1h")
    assert result["window"] == "1h"
    assert result["total_tokens"] == 50 + sum(range(5))  # 10+11+12+13+14 = 60
    assert len(result["by_agent"]) == 5


async def test_usage_global_top_n(db_session) -> None:  # type: ignore[no-untyped-def]
    """12 agents → group_by_agent_global top_n=10 返回 10 个 + 排序降序。"""
    await _seed_records(db_session, n=12, hours_ago=0.0)
    svc = UsageService(PostgresUsageRepository(db_session))
    result = await svc.aggregate_global(window_name="1h", top_n=10)
    assert len(result["by_agent"]) == 10
    tokens = [r["total_tokens"] for r in result["by_agent"]]
    assert tokens == sorted(tokens, reverse=True)


def test_usage_global_window_validation() -> None:
    """HTTP GET /api/usage/global?window=invalid → 422。"""
    from app.main import app  # noqa: F401  (触发 usage.router 注册)

    with TestClient(app) as client:
        resp = client.get("/api/usage/global?window=invalid")
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
