"""McpServerService（L3）：MCP F3 创建用例（路径 A, owner 特批）。

按 04-commands §2.6 契约：
- POST /api/mcp/servers 接受 McpServerCreateRequest
- dry_run=true: schema 校验 + 沙箱探测（30s CPU=1 Mem=512MB net=none，本期 path A mock 探针）
- dry_run=false: 直接落 status=draft

R3 鉴权：JWT 仅解析，不强制（无 membership 模型）。
"""
from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import DomainError, ValidationError
from app.domain.enums import McpServerStatus, McpTransport
from app.domain.mcp.mcp_server import McpServer
from app.domain.mcp.rules import validate_install_config, validate_version
from app.domain.repositories import McpServerRepository

SLUG_RE = re.compile(r"^[a-z0-9-]+$")


class McpServerService:
    def __init__(self, server_repo: McpServerRepository) -> None:
        self._repo = server_repo

    async def create(
        self,
        *,
        name: str,
        slug: str,
        transport: str,
        config_json: dict,
        version: str = "1.0.0",
        description: str = "",
        tags: list[str] | None = None,
        template_id: UUID | None = None,
        dry_run: bool = True,
        created_by: UUID | None = None,
    ) -> tuple[McpServer, dict | None]:
        """创建 MCP server（draft）。返回 (server, dry_run_result)。"""
        # (1) slug 格式
        if not SLUG_RE.match(slug):
            raise ValidationError(f"E_MCP_SCHEMA_INVALID: slug '{slug}' 不匹配 ^[a-z0-9-]+$")
        # (2) version
        try:
            validate_version(version)
        except DomainError as e:
            raise ValidationError(f"E_MCP_VERSION_TOO_LONG: {e}") from e
        # (3) transport 枚举 + 配置结构
        try:
            transport_enum = McpTransport(transport)
        except ValueError as e:
            raise ValidationError(f"E_MCP_SCHEMA_INVALID: 未知 transport '{transport}'") from e
        validate_install_config(transport, config_json)
        # (4) slug 唯一
        existing = await self._repo.get_by_slug(slug)
        if existing is not None:
            raise ValidationError(f"E_MCP_SLUG_CONFLICT: slug '{slug}' 已存在")
        # (5) 构造（__post_init__ 跑 validate + 算 args_hash）
        server = McpServer(
            name=name,
            slug=slug,
            transport=transport_enum,
            config_json=config_json,
            config_schema={},
            version=version,
            description=description,
            tags=tags or [],
            status=McpServerStatus.DRAFT,
            created_by=created_by,
        )
        # (6) dry_run 探针（mock 沙箱）
        dry_run_result: dict | None = None
        if dry_run:
            dry_run_result = await self._run_dry_run_probe(server)
        # (7) 落库 draft
        await self._repo.save(server)
        return server, dry_run_result

    async def _run_dry_run_probe(self, server: McpServer) -> dict:
        """沙箱探针 mock 实现（per 04-commands §2.6 F3 dry_run 限额）。

        生产需起单 Docker 容器（30s CPU=1 Mem=512MB net=none）。
        path A 用 asyncio.wait_for 模拟 30s timeout + 返回 schema 校验结果。
        """
        try:
            await asyncio.wait_for(asyncio.sleep(0), timeout=30.0)
        except asyncio.TimeoutError as e:
            raise ValidationError("E_MCP_DRY_RUN_TIMEOUT: 30s 限额超时") from e
        return {
            "ok": True,
            "transport": str(server.transport),
            "args_hash": server.args_hash,
            "checked_at": datetime.now(UTC).isoformat(),
            "limits": {"timeout_s": 30, "cpu": 1, "mem_mb": 512, "net": "none"},
            "notes": "path-A mock 探针（无真 Docker）；schema 校验在 service.create() 已完成",
        }
