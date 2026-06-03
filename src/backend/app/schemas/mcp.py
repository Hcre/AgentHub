"""MCP 相关 Schema（Pydantic v2，AP-04）。

契约对齐 `docs/specs/04-commands` §2.6（PR-01）。R1：`workspace_id` 实为 session_id
（workspace 维度 stand-in）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.mcp.mcp_binding import AgentMcpBinding
from app.domain.mcp.mcp_installation import WorkspaceMcpInstallation
from app.domain.mcp.mcp_server import McpServer


class McpMarketItemOut(BaseModel):
    mcp_id: UUID
    name: str
    slug: str
    description: str
    transport: str
    version: str
    tags: list[str]
    official: bool
    install_count: int

    @classmethod
    def from_domain(cls, s: McpServer) -> McpMarketItemOut:
        return cls(
            mcp_id=s.id,
            name=s.name,
            slug=s.slug,
            description=s.description,
            transport=str(s.transport),
            version=s.version,
            tags=s.tags,
            official=s.official,
            install_count=s.install_count,
        )


class McpMarketListOut(BaseModel):
    items: list[McpMarketItemOut]
    total: int
    page: int
    page_size: int


class McpServerDetailOut(BaseModel):
    mcp_id: UUID
    name: str
    slug: str
    description: str
    transport: str
    config_schema: dict
    version: str
    tags: list[str]
    official: bool
    status: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    dry_run_result: dict | None

    @classmethod
    def from_domain(cls, s: McpServer) -> McpServerDetailOut:
        return cls(
            mcp_id=s.id,
            name=s.name,
            slug=s.slug,
            description=s.description,
            transport=str(s.transport),
            config_schema=s.config_schema,
            version=s.version,
            tags=s.tags,
            official=s.official,
            status=str(s.status),
            created_by=s.created_by,
            created_at=s.created_at,
            updated_at=s.updated_at,
            dry_run_result=s.dry_run_result,
        )


class McpTemplateOut(BaseModel):
    template_id: UUID  # 本期 = official MCP 的 mcp_id
    name: str
    transport: str
    version: str
    tags: list[str]
    mcp_config: dict

    @classmethod
    def from_domain(cls, s: McpServer) -> McpTemplateOut:
        return cls(
            template_id=s.id,
            name=s.name,
            transport=str(s.transport),
            version=s.version,
            tags=s.tags,
            mcp_config=s.config_json,
        )


class McpTemplateListOut(BaseModel):
    templates: list[McpTemplateOut]


class McpInstallRequest(BaseModel):
    workspace_id: UUID  # R1：传 session_id
    mcp_id: UUID
    instance_name: str = Field(min_length=1, max_length=128)
    config_overrides: dict | None = None


class McpInstallationOut(BaseModel):
    installation_id: UUID
    status: str
    mcp_id: UUID
    instance_name: str
    created_at: datetime

    @classmethod
    def from_domain(cls, i: WorkspaceMcpInstallation) -> McpInstallationOut:
        return cls(
            installation_id=i.id,
            status=str(i.status),
            mcp_id=i.mcp_id,
            instance_name=i.instance_name,
            created_at=i.created_at,
        )


class McpBindRequest(BaseModel):
    agent_id: UUID
    installation_id: UUID
    tool_subset: list[str] | None = None  # 省略=暴露全部 tool


class McpBindingOut(BaseModel):
    binding_id: UUID
    agent_id: UUID
    installation_id: UUID
    tool_subset: list[str]
    status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, b: AgentMcpBinding) -> McpBindingOut:
        return cls(
            binding_id=b.id,
            agent_id=b.agent_id,
            installation_id=b.installation_id,
            tool_subset=b.tool_subset,
            status=str(b.status),
            created_at=b.created_at,
        )
