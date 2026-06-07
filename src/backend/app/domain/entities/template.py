"""Template 领域实体。

Template: Agent 模板（从 wshobson/skills 等源仓库同步）。
TemplateSource: 模板源仓库注册信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.exceptions import DomainError


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Template:
    """Agent 模板实体。source_path 为仓库内相对路径（如 skills/vibe-xhs）。"""

    source_path: str
    name: str
    id: UUID = field(default_factory=uuid4)
    source: str = "wshobson"
    description: str = ""
    model_tier: str = "inherit"
    tools: list[str] = field(default_factory=list)
    color: str | None = None
    display_name_zh: str | None = None
    description_zh: str | None = None
    recommended_skills: list[str] = field(default_factory=list)
    compatible_agent_systems: list[str] = field(default_factory=list)
    compatible_providers: list[str] = field(default_factory=list)
    is_enabled: bool = True
    is_favorite: bool = False
    favorite_name: str | None = None
    favorite_description: str | None = None
    favorite_order: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainError("Template name 不能为空")
        if not self.source_path or not self.source_path.strip():
            raise DomainError("Template source_path 不能为空")
        if self.model_tier not in ("opus", "sonnet", "haiku", "inherit"):
            raise DomainError("Template model_tier 必须为 opus/sonnet/haiku/inherit 之一")

    def update(self, **changed: object) -> list[str]:
        """部分更新，返回实际变更的字段名列表。"""
        allowed = {
            "name",
            "description",
            "model_tier",
            "tools",
            "color",
            "display_name_zh",
            "description_zh",
            "recommended_skills",
            "compatible_agent_systems",
            "compatible_providers",
            "is_enabled",
            "is_favorite",
            "favorite_name",
            "favorite_description",
            "favorite_order",
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


@dataclass
class TemplateSource:
    """模板源注册实体。id 即仓库名（如 wshobson/skills 的 'wshobson'）。"""

    id: str
    url: str
    branch: str = "main"
    description_zh: str | None = None
    enabled: bool = True
    template_count: int = 0
    last_synced: datetime | None = None
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.id or not self.id.strip():
            raise DomainError("TemplateSource id 不能为空")
        if not self.url or not self.url.strip():
            raise DomainError("TemplateSource url 不能为空")

    def update(self, **changed: object) -> list[str]:
        """部分更新，返回实际变更的字段名列表。"""
        allowed = {
            "url",
            "branch",
            "description_zh",
            "enabled",
            "template_count",
            "last_synced",
        }
        changed_fields: list[str] = []
        for key, value in changed.items():
            if value is None or key not in allowed:
                continue
            if getattr(self, key) != value:
                setattr(self, key, value)
                changed_fields.append(key)
        if changed_fields:
            self.validate()
        return changed_fields
