"""MCP 路由（L4，PR-01 §2.6）：市场浏览/详情 + 安装。

URL 前缀 `/api/mcp`（无 `/v1/`，ADR-0003）。错误体沿用全库 `{detail}`（R9）。
鉴权仅 JWT 解析、无成员校验（R3）。本期 3 端点：list / detail / install。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    CurrentUser,
    get_mcp_binding_service,
    get_mcp_install_service,
    get_mcp_market_service,
    get_mcp_server_service,
)
from app.application.services.mcp_binding_service import McpBindingService
from app.application.services.mcp_install_service import McpInstallService
from app.application.services.mcp_market_service import McpMarketService
from app.application.services.mcp_server_service import McpServerService
from app.schemas.mcp import (
    McpBindingOut,
    McpBindRequest,
    McpInstallationOut,
    McpInstallRequest,
    McpMarketItemOut,
    McpMarketListOut,
    McpServerCreateRequest,
    McpServerDetailOut,
    McpServerOut,
    McpTemplateListOut,
    McpTemplateOut,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

MarketSvc = Annotated[McpMarketService, Depends(get_mcp_market_service)]
InstallSvc = Annotated[McpInstallService, Depends(get_mcp_install_service)]
BindingSvc = Annotated[McpBindingService, Depends(get_mcp_binding_service)]
ServerSvc = Annotated[McpServerService, Depends(get_mcp_server_service)]

_MAX_PAGE_SIZE = 100


@router.get("/market", response_model=McpMarketListOut)
async def list_market(
    svc: MarketSvc,
    _user: CurrentUser,
    workspace_id: Annotated[UUID, Query(description="session_id（workspace 维度 stand-in，R1）")],
    q: str | None = None,
    tag: str | None = None,
    transport: str | None = None,
    official_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE),
) -> McpMarketListOut:
    items, total = await svc.list_market(
        q=q,
        tag=tag,
        transport=transport,
        official_only=official_only,
        page=page,
        page_size=page_size,
    )
    return McpMarketListOut(
        items=[McpMarketItemOut.from_domain(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/market/templates", response_model=McpTemplateListOut)
async def list_templates(
    svc: MarketSvc,
    _user: CurrentUser,
    workspace_id: Annotated[UUID, Query(description="session_id（workspace 维度 stand-in，R1）")],
) -> McpTemplateListOut:
    templates = await svc.list_templates()
    return McpTemplateListOut(templates=[McpTemplateOut.from_domain(s) for s in templates])


@router.get("/market/{mcp_id}", response_model=McpServerDetailOut)
async def get_market_detail(
    mcp_id: UUID,
    svc: MarketSvc,
    _user: CurrentUser,
) -> McpServerDetailOut:
    return McpServerDetailOut.from_domain(await svc.get_detail(mcp_id))


@router.post(
    "/installations",
    response_model=McpInstallationOut,
    status_code=status.HTTP_201_CREATED,
)
async def install_mcp(
    body: McpInstallRequest,
    svc: InstallSvc,
    user: CurrentUser,
) -> McpInstallationOut:
    installation = await svc.install(
        workspace_id=body.workspace_id,
        mcp_id=body.mcp_id,
        instance_name=body.instance_name,
        config_overrides=body.config_overrides,
        installed_by=user,
    )
    return McpInstallationOut.from_domain(installation)


@router.delete("/installations/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_mcp(
    installation_id: UUID,
    svc: InstallSvc,
    _user: CurrentUser,
    workspace_id: Annotated[UUID, Query(description="session_id（workspace 维度 stand-in，R1）")],
) -> Response:
    await svc.uninstall(installation_id=installation_id, workspace_id=workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bindings", response_model=McpBindingOut, status_code=status.HTTP_201_CREATED)
async def bind_mcp(
    body: McpBindRequest,
    svc: BindingSvc,
    _user: CurrentUser,
) -> McpBindingOut:
    # 副作用（请求携带）：下次该 agent 的 stream 自动挂载，无需运行时有状态 attach（ADR-05）
    binding = await svc.bind(
        agent_id=body.agent_id,
        installation_id=body.installation_id,
        tool_subset=body.tool_subset,
    )
    return McpBindingOut.from_domain(binding)


@router.delete("/bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_mcp(
    binding_id: UUID,
    svc: BindingSvc,
    _user: CurrentUser,
) -> Response:
    await svc.unbind(binding_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── F3 创建（路径 A, owner 特批 @2026-06-08 23:03 SLA 落地）──


@router.post(
    "/servers",
    response_model=McpServerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server(
    body: McpServerCreateRequest,
    svc: ServerSvc,
    user: CurrentUser,
) -> McpServerOut:
    """04-commands §2.6 F3：创建 MCP server（draft）。dry_run 默认 True 走沙箱探针。"""
    server, dry_run_result = await svc.create(
        name=body.name,
        slug=body.slug,
        transport=body.transport,
        config_json=body.config_json,
        version=body.version,
        description=body.description,
        tags=body.tags,
        template_id=body.template_id,
        dry_run=body.dry_run,
        created_by=user,
    )
    return McpServerOut.from_domain(server, dry_run_result=dry_run_result)


# ── F3 创建（路径 A, owner 特批 @2026-06-08 23:03 SLA 落地）──


@router.post(
    "/servers",
    response_model=McpServerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server(
    body: McpServerCreateRequest,
    svc: ServerSvc,
    user: CurrentUser,
) -> McpServerOut:
    """04-commands §2.6 F3：创建 MCP server（draft）。dry_run 默认 True 走沙箱探针。"""
    server, dry_run_result = await svc.create(
        name=body.name,
        slug=body.slug,
        transport=body.transport,
        config_json=body.config_json,
        version=body.version,
        description=body.description,
        tags=body.tags,
        template_id=body.template_id,
        dry_run=body.dry_run,
        created_by=user,
    )
    return McpServerOut.from_domain(server, dry_run_result=dry_run_result)
