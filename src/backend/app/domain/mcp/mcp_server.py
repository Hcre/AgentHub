"""MCPServer 实体（MD-MCP §1.1）：MCP 市场元数据聚合根。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.exceptions import DomainError
from app.domain.enums import McpServerStatus, McpTransport
from app.domain.mcp.rules import compute_args_hash, validate_version


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class McpServer:
    """MCP server 元数据。args_hash 由 config_json 派生（幂等去重）。"""

    name: str
    slug: str
    transport: McpTransport
    config_schema: dict[str, Any] = field(default_factory=dict)
    config_json: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    official: bool = False
    latest: bool = True
    status: McpServerStatus = McpServerStatus.DRAFT
    created_by: UUID | None = None  # R2：JWT sub，裸 UUID 无 FK
    dry_run_result: dict[str, Any] | None = None
    dry_run_at: datetime | None = None
    install_count: int = 0
    args_hash: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.args_hash:
            self.args_hash = compute_args_hash(self.config_json)
        self.validate()

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainError("MCP name 不能为空")
        if not self.slug or not self.slug.strip():
            raise DomainError("MCP slug 不能为空")
        validate_version(self.version)
