"""AgentMcpBinding 实体（MD-MCP §1.3）：Agent 与已安装 MCP 的绑定。

解绑为软删（status=removed + unbound_at），保留审计。tool_subset 为空表示全选。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.enums import McpBindingStatus


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class AgentMcpBinding:
    agent_id: UUID
    installation_id: UUID
    tool_subset: list[str] = field(default_factory=list)  # 空=暴露 MCP 全部 tool
    status: McpBindingStatus = McpBindingStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    unbound_at: datetime | None = None

    def unbind(self) -> None:
        """软删：标记 removed 并记录解绑时间（F-009/F-011）。"""
        self.status = McpBindingStatus.REMOVED
        self.unbound_at = _now()
        self.updated_at = self.unbound_at
