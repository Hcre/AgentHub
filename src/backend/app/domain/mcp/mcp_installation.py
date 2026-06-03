"""WorkspaceMcpInstallation 实体（MD-MCP §1.2）：工作区维度的 MCP 安装。

R1（二次对账）：现库无 workspaces 表，`workspace_id` 暂存 `session_id` 作 stand-in，
裸 UUID 无 FK。`args_hash` 由 config_overrides 派生，支撑安装幂等键
(workspace_id + mcp_id + args_hash)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.exceptions import DomainError
from app.domain.enums import McpInstallStatus
from app.domain.mcp.rules import compute_args_hash


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class WorkspaceMcpInstallation:
    workspace_id: UUID  # R1：暂存 session_id
    mcp_id: UUID
    instance_name: str
    installed_by: UUID | None = None  # R2：JWT sub，裸 UUID 无 FK
    config_overrides: dict[str, Any] = field(default_factory=dict)
    status: McpInstallStatus = McpInstallStatus.INSTALLING
    error_code: str | None = None
    error_message: str | None = None
    args_hash: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    last_health_check_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.args_hash:
            self.args_hash = compute_args_hash(self.config_overrides)
        self.validate()

    def validate(self) -> None:
        if not self.instance_name or not self.instance_name.strip():
            raise DomainError("MCP instance_name 不能为空")

    def mark_ready(self) -> None:
        self.status = McpInstallStatus.READY
        self.updated_at = _now()

    def mark_failed(self, code: str, message: str) -> None:
        self.status = McpInstallStatus.FAILED
        self.error_code = code
        self.error_message = message
        self.updated_at = _now()
