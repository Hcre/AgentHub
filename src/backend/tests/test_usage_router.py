"""P1-2 /api/usage router 注册 smoke test（t9-usage-router-register track）。

背景: 2026-06-08 overnight plan (plan_3eaba0fa) 落 4 端点 + token 监控全栈
实现，但 main.py 漏 include_router(usage.router)，前端 /api/usage 调用
404。本测试验证 router 已注册 + 端点可达。

3 路径（per Task brief）：
1. test_usage_router_registered — 导入 app.main 不抛 ImportError（router 已注册）
2. test_usage_endpoint_reachable — GET /api/usage（无参数）→ 422
   （E_USAGE_PARAMS_MISSING 错误，证明端点存在 + 业务校验生效）
3. test_usage_window_validation — GET /api/usage?window=invalid → 422
   （E_USAGE_WINDOW_INVALID 错误，证明 query pattern 校验生效）

注意: 完整 E2E（4 window + 触发点验证）见 test_usage_e2e.py。
本文件只覆盖"router 已挂到 FastAPI app"这一最基础烟测。
"""

from __future__ import annotations

import base64
import os

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

from fastapi.testclient import TestClient


def test_usage_router_registered() -> None:
    """导入 app.main 不抛 ImportError，证明 usage router 已注册。"""
    from app.main import app  # noqa: F401

    # 检查路由表中有 /api/usage 路径
    paths = {route.path for route in app.routes}
    assert "/api/usage" in paths, (
        f"/api/usage router not registered. Available paths: "
        f"{sorted(p for p in paths if p.startswith('/api'))}"
    )


def test_usage_endpoint_reachable() -> None:
    """GET /api/usage（无参数）→ 422，证明端点存在 + 业务校验生效。"""
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/usage")
    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail", "")
    # FastAPI 422 for missing required query params
    assert "agent_id" in str(detail) or "session_id" in str(detail), (
        f"Expected missing-param error, got: {detail}"
    )


def test_usage_window_validation() -> None:
    """GET /api/usage?window=invalid → 422，证明 query pattern 校验生效。"""
    from app.main import app

    # 用 UUID 格式占位 + 非法 window（绕过 missing-param 422 优先于 window 422）
    with TestClient(app) as client:
        resp = client.get("/api/usage?agent_id=00000000-0000-0000-0000-000000000000&window=invalid")
    # window=invalid 不在 ^(1h|24h|7d)$ pattern 内 → 422
    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail", [])
    # FastAPI 422 for query pattern mismatch
    assert any("window" in str(item) for item in detail), (
        f"Expected window pattern error, got: {detail}"
    )
