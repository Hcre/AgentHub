"""MCP 接入 P1 测试（domain 规则 + market/install 服务，L3 + L1 SQLite）。

覆盖三路径（T-03）：正常 / 边界 / 异常。R1：workspace_id 传 session_id。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services import McpInstallService, McpMarketService
from app.core.exceptions import DomainError, NotFoundError, ValidationError
from app.domain.enums import McpInstallStatus, McpServerStatus, McpTransport
from app.domain.mcp.mcp_server import McpServer
from app.domain.mcp.rules import compute_args_hash, validate_batch_size, validate_version
from app.infrastructure.db.models import AgentMcpBindingModel
from app.infrastructure.repositories import (
    PostgresMcpInstallationRepository,
    PostgresMcpServerRepository,
)

# --- domain 规则（无 DB）---


def test_compute_args_hash_is_order_independent() -> None:
    a = compute_args_hash({"b": 2, "a": 1})
    b = compute_args_hash({"a": 1, "b": 2})
    assert a == b
    assert len(a) == 64  # 对齐 String(64)


def test_compute_args_hash_distinguishes_content() -> None:
    assert compute_args_hash({"a": 1}) != compute_args_hash({"a": 2})
    assert compute_args_hash(None) == compute_args_hash({})


def test_validate_version_too_long_raises() -> None:
    validate_version("1.0.0")  # 正常
    with pytest.raises(ValidationError):
        validate_version("v" * 51)
    with pytest.raises(DomainError):
        validate_version("")


def test_validate_batch_size_boundary() -> None:
    validate_batch_size(50)  # 边界允许
    with pytest.raises(ValidationError):
        validate_batch_size(51)


# --- helpers ---


async def _seed_server(
    repo: PostgresMcpServerRepository,
    *,
    name: str,
    slug: str,
    transport: McpTransport = McpTransport.STDIO,
    status: McpServerStatus = McpServerStatus.PUBLISHED,
    official: bool = False,
    tags: list[str] | None = None,
    install_count: int = 0,
) -> McpServer:
    server = McpServer(
        name=name,
        slug=slug,
        transport=transport,
        status=status,
        official=official,
        tags=tags or [],
        install_count=install_count,
        config_json={"cmd": name},
    )
    await repo.save(server)
    return server


# --- market 服务 ---


@pytest.mark.asyncio
async def test_market_lists_only_published(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresMcpServerRepository(db_session)
    await _seed_server(repo, name="Pub", slug="pub", status=McpServerStatus.PUBLISHED)
    await _seed_server(repo, name="Draft", slug="draft", status=McpServerStatus.DRAFT)
    svc = McpMarketService(repo)

    items, total = await svc.list_market()
    assert total == 1
    assert items[0].name == "Pub"


@pytest.mark.asyncio
async def test_market_filters_and_pagination(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresMcpServerRepository(db_session)
    await _seed_server(repo, name="Alpha", slug="alpha", tags=["fs"], official=True)
    await _seed_server(repo, name="Beta", slug="beta", tags=["web"], transport=McpTransport.SSE)
    await _seed_server(repo, name="Gamma", slug="gamma", tags=["fs"])
    svc = McpMarketService(repo)

    # q 过滤
    items, total = await svc.list_market(q="lph")
    assert total == 1 and items[0].name == "Alpha"
    # tag 过滤（Python 侧）
    _, total_fs = await svc.list_market(tag="fs")
    assert total_fs == 2
    # transport 过滤
    _, total_sse = await svc.list_market(transport="sse")
    assert total_sse == 1
    # official_only
    _, total_official = await svc.list_market(official_only=True)
    assert total_official == 1
    # 分页：page_size=2 → 第二页 1 条
    page2, total_all = await svc.list_market(page=2, page_size=2)
    assert total_all == 3 and len(page2) == 1


@pytest.mark.asyncio
async def test_market_detail_found_and_missing(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresMcpServerRepository(db_session)
    server = await _seed_server(repo, name="Detail", slug="detail")
    svc = McpMarketService(repo)

    got = await svc.get_detail(server.id)
    assert got.id == server.id
    with pytest.raises(NotFoundError):
        await svc.get_detail(uuid4())


# --- install 服务 ---


def _install_service(db) -> McpInstallService:  # type: ignore[no-untyped-def]
    return McpInstallService(PostgresMcpServerRepository(db), PostgresMcpInstallationRepository(db))


@pytest.mark.asyncio
async def test_install_creates_ready(db_session) -> None:  # type: ignore[no-untyped-def]
    server = await _seed_server(PostgresMcpServerRepository(db_session), name="S", slug="s")
    svc = _install_service(db_session)
    ws = uuid4()  # session_id stand-in

    inst = await svc.install(workspace_id=ws, mcp_id=server.id, instance_name="my-fs")
    assert inst.status == McpInstallStatus.READY
    assert inst.workspace_id == ws


@pytest.mark.asyncio
async def test_install_is_idempotent(db_session) -> None:  # type: ignore[no-untyped-def]
    server = await _seed_server(PostgresMcpServerRepository(db_session), name="S", slug="s")
    svc = _install_service(db_session)
    ws = uuid4()

    first = await svc.install(
        workspace_id=ws, mcp_id=server.id, instance_name="fs", config_overrides={"k": 1}
    )
    second = await svc.install(
        workspace_id=ws, mcp_id=server.id, instance_name="fs-other", config_overrides={"k": 1}
    )
    # 同 args_hash → 返回同一安装（不因 instance_name 不同而新建）
    assert second.id == first.id


@pytest.mark.asyncio
async def test_install_name_conflict(db_session) -> None:  # type: ignore[no-untyped-def]
    server = await _seed_server(PostgresMcpServerRepository(db_session), name="S", slug="s")
    svc = _install_service(db_session)
    ws = uuid4()

    await svc.install(
        workspace_id=ws, mcp_id=server.id, instance_name="dup", config_overrides={"k": 1}
    )
    # 同 workspace 同 instance_name 但不同 config（不同 args_hash）→ 409 冲突
    with pytest.raises(DomainError):
        await svc.install(
            workspace_id=ws, mcp_id=server.id, instance_name="dup", config_overrides={"k": 2}
        )


@pytest.mark.asyncio
async def test_install_mcp_not_found(db_session) -> None:  # type: ignore[no-untyped-def]
    svc = _install_service(db_session)
    with pytest.raises(NotFoundError):
        await svc.install(workspace_id=uuid4(), mcp_id=uuid4(), instance_name="x")


# --- templates + uninstall ---


@pytest.mark.asyncio
async def test_templates_lists_official_published_only(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = PostgresMcpServerRepository(db_session)
    await _seed_server(repo, name="Off", slug="off", official=True)
    await _seed_server(repo, name="Community", slug="comm", official=False)
    await _seed_server(
        repo, name="OffDraft", slug="offdraft", official=True, status=McpServerStatus.DRAFT
    )
    svc = McpMarketService(repo)

    templates = await svc.list_templates()
    assert [t.name for t in templates] == ["Off"]


@pytest.mark.asyncio
async def test_uninstall_removes(db_session) -> None:  # type: ignore[no-untyped-def]
    server = await _seed_server(PostgresMcpServerRepository(db_session), name="S", slug="s")
    svc = _install_service(db_session)
    ws = uuid4()
    inst = await svc.install(workspace_id=ws, mcp_id=server.id, instance_name="fs")

    await svc.uninstall(installation_id=inst.id, workspace_id=ws)
    assert await PostgresMcpInstallationRepository(db_session).get_by_id(inst.id) is None


@pytest.mark.asyncio
async def test_uninstall_missing_or_cross_workspace_raises(db_session) -> None:  # type: ignore[no-untyped-def]
    server = await _seed_server(PostgresMcpServerRepository(db_session), name="S", slug="s")
    svc = _install_service(db_session)
    inst = await svc.install(workspace_id=uuid4(), mcp_id=server.id, instance_name="fs")

    with pytest.raises(NotFoundError):
        await svc.uninstall(installation_id=uuid4(), workspace_id=uuid4())
    # 跨 workspace 视为不存在
    with pytest.raises(NotFoundError):
        await svc.uninstall(installation_id=inst.id, workspace_id=uuid4())


@pytest.mark.asyncio
async def test_uninstall_blocked_by_active_binding(db_session) -> None:  # type: ignore[no-untyped-def]
    server = await _seed_server(PostgresMcpServerRepository(db_session), name="S", slug="s")
    svc = _install_service(db_session)
    ws = uuid4()
    inst = await svc.install(workspace_id=ws, mcp_id=server.id, instance_name="fs")
    # 直插一条 active 绑定（绑定服务 P2，SQLite 不强制 FK）
    db_session.add(
        AgentMcpBindingModel(
            agent_id=uuid4(), installation_id=inst.id, status="active", tool_subset=[]
        )
    )
    await db_session.flush()

    with pytest.raises(DomainError):
        await svc.uninstall(installation_id=inst.id, workspace_id=ws)


# --- 路由注册（无 DB，验证 L4 装配）---


def test_mcp_routes_registered() -> None:
    from app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/mcp/market" in paths
    assert "/api/mcp/market/templates" in paths
    assert "/api/mcp/market/{mcp_id}" in paths
    assert "/api/mcp/installations" in paths
    assert "/api/mcp/installations/{installation_id}" in paths
