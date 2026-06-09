"""MCP F3 创建 server 测试（04-commands §2.6, t3 路径 A 落地, owner 特批 @23:03 SLA）。

4 路径：
1. happy path: dry_run=true → 201 字段齐 + status=draft + dry_run_result.ok=True
2. 字段校验失败: slug 不匹配 ^[a-z0-9-]+$ → ValidationError
3. transport 校验失败: unknown transport → ValidationError
4. slug 冲突: 同 slug 二次创建 → ValidationError(E_MCP_SLUG_CONFLICT)
"""
from __future__ import annotations

import base64
import os

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import pytest

from app.application.services.mcp_server_service import McpServerService
from app.core.exceptions import ValidationError
from app.domain.mcp.mcp_server import McpServer
from app.domain.repositories import McpServerRepository


class _InMemoryServerRepo(McpServerRepository):
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_slug: dict = {}

    async def save(self, server: McpServer) -> None:
        self._by_id[server.id] = server
        self._by_slug[server.slug] = server

    async def get_by_id(self, mcp_id):
        return self._by_id.get(mcp_id)

    async def get_by_slug(self, slug):
        return self._by_slug.get(slug)

    async def exists_by_name(self, name):
        return any(s.name == name for s in self._by_id.values())

    async def list_market(self, **_):
        return [], 0

    async def list_templates(self):
        return []


@pytest.mark.asyncio
async def test_create_dry_run_happy_path():
    """路径 1: dry_run=True → 201 字段齐 + status=draft + dry_run_result.ok=True。"""
    repo = _InMemoryServerRepo()
    svc = McpServerService(repo)
    server, dry = await svc.create(
        name="test-mcp",
        slug="test-mcp",
        transport="stdio",
        config_json={"command": "node server.js"},
        version="1.0.0",
        dry_run=True,
    )
    assert server.status.value == "draft"
    assert server.slug == "test-mcp"
    assert server.args_hash != ""
    assert dry is not None
    assert dry["ok"] is True
    assert dry["transport"] == "stdio"
    assert dry["limits"]["timeout_s"] == 30
    reloaded = await repo.get_by_slug("test-mcp")
    assert reloaded is not None
    assert reloaded.id == server.id


@pytest.mark.asyncio
async def test_create_slug_invalid_pattern():
    """路径 2: slug 含大写 / 下划线 → ValidationError(E_MCP_SCHEMA_INVALID)。"""
    svc = McpServerService(_InMemoryServerRepo())
    with pytest.raises(ValidationError) as exc:
        await svc.create(
            name="bad",
            slug="Bad_Slug",
            transport="stdio",
            config_json={"command": "x"},
            dry_run=False,
        )
    assert "E_MCP_SCHEMA_INVALID" in str(exc.value)


@pytest.mark.asyncio
async def test_create_transport_invalid():
    """路径 3: transport 不是 stdio/sse/streamable_http → ValidationError。"""
    svc = McpServerService(_InMemoryServerRepo())
    with pytest.raises(ValidationError) as exc:
        await svc.create(
            name="x",
            slug="x-y",
            transport="websocket",
            config_json={"command": "x"},
            dry_run=False,
        )
    assert "E_MCP_SCHEMA_INVALID" in str(exc.value)


@pytest.mark.asyncio
async def test_create_slug_conflict():
    """路径 4: 第二次同 slug → ValidationError(E_MCP_SLUG_CONFLICT)。"""
    repo = _InMemoryServerRepo()
    svc = McpServerService(repo)
    await svc.create(
        name="a",
        slug="dup-slug",
        transport="stdio",
        config_json={"command": "x"},
        dry_run=False,
    )
    with pytest.raises(ValidationError) as exc:
        await svc.create(
            name="b",
            slug="dup-slug",
            transport="stdio",
            config_json={"command": "y"},
            dry_run=False,
        )
    assert "E_MCP_SLUG_CONFLICT" in str(exc.value)
