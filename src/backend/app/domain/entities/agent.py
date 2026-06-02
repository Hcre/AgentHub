"""Agent 聚合根。

PRD §2.1：创建必填 name/avatar/role/provider/model/api_key；
系统维护 id/status/workload/channels/workspace 等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.exceptions import DomainError
from app.domain.enums import AgentStatus, AgentSystem, Provider


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Agent:
    """Agent 聚合根。api_key 以密文形式持有，明文加密由 L3 完成。"""

    name: str
    avatar: str
    role: str
    agent_system: AgentSystem = AgentSystem.MOCK
    provider: Provider = Provider.ANTHROPIC
    model: str = ""
    api_key_encrypted: str = ""
    base_url: str | None = None
    id: UUID = field(default_factory=uuid4)
    skills: list[str] = field(default_factory=list)
    capability_tags: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    status: AgentStatus = AgentStatus.OFFLINE
    workload: int = 0
    is_system: bool = False
    settings: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainError("Agent name 不能为空")
        # CLI 运行时（claude_code/pi_agent/opencode）和 mock 不需要 API key
        needs_api_key = self.agent_system in (
            AgentSystem.ANTHROPIC_API,
            AgentSystem.OPENAI_API,
        )
        if not self.is_system and needs_api_key and not self.api_key_encrypted:
            raise DomainError("API 模式 Agent 必须提供 api_key")

    def update(self, **changed: object) -> list[str]:
        """部分更新，返回实际变更的字段名列表（用于 AgentUpdated 事件）。"""
        allowed = {
            "name",
            "avatar",
            "role",
            "agent_system",
            "provider",
            "model",
            "api_key_encrypted",
            "base_url",
            "skills",
            "capability_tags",
            "system_prompt",
            "settings",
            "status",
        }
        changed_fields: list[str] = []
        for key, value in changed.items():
            if value is None or key not in allowed:
                continue
            if getattr(self, key) != value:
                setattr(self, key, value)
                changed_fields.append(key)
        if changed_fields:
            self.updated_at = _now()
            self.validate()
        return changed_fields
