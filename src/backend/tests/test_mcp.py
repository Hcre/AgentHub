"""MCP 接入 P1 测试（domain 规则 + market/install 服务，L3 + L1 SQLite）。

覆盖三路径（T-03）：正常 / 边界 / 异常。R1：workspace_id 传 session_id。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services import (
    McpBindingService,
    McpInstallService,
    McpMarketService,
)
from app.core.exceptions import DomainError, NotFoundError, ValidationError
from app.domain.enums import (
    McpBindingStatus,
    McpInstallStatus,
    McpServerStatus,
    McpTransport,
)
from app.domain.mcp.mcp_server import McpServer
from app.domain.mcp.rules import (
    build_mcp_config_entry,
    compute_args_hash,
    validate_batch_size,
    validate_install_config,
    validate_version,
)
from app.infrastructure.db.models import AgentMcpBindingModel
from app.infrastructure.mcp import LocalMcpInstaller
from app.infrastructure.repositories import (
    PostgresMcpBindingRepository,
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


def test_validate_install_config_by_transport() -> None:
    validate_install_config("stdio", {"command": "npx"})  # ok
    validate_install_config("sse", {"url": "https://x/mcp"})  # ok
    validate_install_config("streamable_http", {"url": "http://x/mcp"})  # ok
    with pytest.raises(ValidationError):
        validate_install_config("stdio", {})  # 缺 command
    with pytest.raises(ValidationError):
        validate_install_config("sse", {"url": "ftp://x"})  # 非 http(s)
    with pytest.raises(ValidationError):
        validate_install_config("bogus", {})  # 未知 transport


# --- helpers ---


def _default_config(transport: McpTransport) -> dict:
    if transport == McpTransport.STDIO:
        return {"command": "echo", "args": ["mcp"]}
    return {"url": "https://example.com/mcp"}


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
    config_json: dict | None = None,
) -> McpServer:
    server = McpServer(
        name=name,
        slug=slug,
        transport=transport,
        status=status,
        official=official,
        tags=tags or [],
        install_count=install_count,
        config_json=config_json if config_json is not None else _default_config(transport),
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
    return McpInstallService(
        PostgresMcpServerRepository(db),
        PostgresMcpInstallationRepository(db),
        LocalMcpInstaller(),
    )


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


@pytest.mark.asyncio
async def test_install_rejects_invalid_server_config(db_session) -> None:  # type: ignore[no-untyped-def]
    # stdio 但 config_json 无 command → 安装探针结构校验失败（422）
    server = await _seed_server(
        PostgresMcpServerRepository(db_session), name="Bad", slug="bad", config_json={}
    )
    svc = _install_service(db_session)
    with pytest.raises(ValidationError):
        await svc.install(workspace_id=uuid4(), mcp_id=server.id, instance_name="bad")


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


# --- P2: 绑定 + 请求携带 config ---


def _binding_service(db) -> McpBindingService:  # type: ignore[no-untyped-def]
    return McpBindingService(
        PostgresMcpBindingRepository(db),
        PostgresMcpInstallationRepository(db),
        PostgresMcpServerRepository(db),
    )


async def _seed_installation(db, *, transport=McpTransport.STDIO):  # type: ignore[no-untyped-def]
    server = await _seed_server(
        PostgresMcpServerRepository(db), name="S", slug="s", transport=transport
    )
    inst = await _install_service(db).install(
        workspace_id=uuid4(), mcp_id=server.id, instance_name="inst"
    )
    return server, inst


def test_build_mcp_config_entry_by_transport() -> None:
    stdio = build_mcp_config_entry(
        "fs", "stdio", {"command": "npx", "args": ["x"], "env": {"K": "v"}}
    )
    assert stdio == {
        "name": "fs",
        "type": "stdio",
        "command": "npx",
        "args": ["x"],
        "env": {"K": "v"},
    }
    sse = build_mcp_config_entry("web", "sse", {"url": "https://x/mcp"})
    assert sse == {"name": "web", "type": "sse", "url": "https://x/mcp"}
    http = build_mcp_config_entry("h", "streamable_http", {"url": "http://x/mcp"})
    assert http["type"] == "http"


@pytest.mark.asyncio
async def test_bind_creates_binding(db_session) -> None:  # type: ignore[no-untyped-def]
    _server, inst = await _seed_installation(db_session)
    agent_id = uuid4()
    binding = await _binding_service(db_session).bind(agent_id=agent_id, installation_id=inst.id)
    assert binding.status == McpBindingStatus.ACTIVE
    assert binding.agent_id == agent_id


@pytest.mark.asyncio
async def test_bind_duplicate_active_conflict(db_session) -> None:  # type: ignore[no-untyped-def]
    _server, inst = await _seed_installation(db_session)
    svc = _binding_service(db_session)
    agent_id = uuid4()
    await svc.bind(agent_id=agent_id, installation_id=inst.id)
    with pytest.raises(DomainError):
        await svc.bind(agent_id=agent_id, installation_id=inst.id)


@pytest.mark.asyncio
async def test_bind_installation_not_found(db_session) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(NotFoundError):
        await _binding_service(db_session).bind(agent_id=uuid4(), installation_id=uuid4())


@pytest.mark.asyncio
async def test_unbind_then_rebind_allowed(db_session) -> None:  # type: ignore[no-untyped-def]
    _server, inst = await _seed_installation(db_session)
    svc = _binding_service(db_session)
    agent_id = uuid4()
    b1 = await svc.bind(agent_id=agent_id, installation_id=inst.id)
    await svc.unbind(b1.id)
    # 部分唯一（status=active）→ 解绑后可再次绑定（F1 rebind 冲突已修）
    b2 = await svc.bind(agent_id=agent_id, installation_id=inst.id)
    assert b2.id != b1.id
    assert b2.status == McpBindingStatus.ACTIVE


@pytest.mark.asyncio
async def test_unbind_missing_404(db_session) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(NotFoundError):
        await _binding_service(db_session).unbind(uuid4())


@pytest.mark.asyncio
async def test_build_request_mcp_servers(db_session) -> None:  # type: ignore[no-untyped-def]
    _server, inst = await _seed_installation(db_session, transport=McpTransport.STDIO)
    svc = _binding_service(db_session)
    agent_id = uuid4()
    await svc.bind(agent_id=agent_id, installation_id=inst.id)

    entries = await svc.build_request_mcp_servers(agent_id)
    assert len(entries) == 1
    assert entries[0]["type"] == "stdio"
    assert entries[0]["command"] == "echo"  # _default_config(stdio)
    # 解绑后不再携带
    binding = await PostgresMcpBindingRepository(db_session).list_active_by_agent(agent_id)
    await svc.unbind(binding[0].id)
    assert await svc.build_request_mcp_servers(agent_id) == []


def test_write_mcp_config_merges_memory_and_bound() -> None:
    import json

    from app.infrastructure.llm.claude_code_runtime import _write_mcp_config

    bound = [{"name": "fs", "type": "stdio", "command": "npx"}]
    path = _write_mcp_config("agent-1", "https://mem/sse", bound)
    assert path is not None
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    assert "agenthub-memory" in cfg["mcpServers"]  # 记忆工具
    assert cfg["mcpServers"]["fs"] == {"type": "stdio", "command": "npx"}  # 绑定（去 name）
    # 无任何 server → None
    assert _write_mcp_config("", "", []) is None


# --- 路由注册（无 DB，验证 L4 装配）---


def test_mcp_routes_registered() -> None:
    from app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/mcp/market" in paths
    assert "/api/mcp/market/templates" in paths
    assert "/api/mcp/market/{mcp_id}" in paths
    assert "/api/mcp/installations" in paths
    assert "/api/mcp/installations/{installation_id}" in paths
    assert "/api/mcp/bindings" in paths
    assert "/api/mcp/bindings/{binding_id}" in paths
