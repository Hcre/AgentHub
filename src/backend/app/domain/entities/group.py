"""Group 聚合根（docs/specs/03-data-model_数据模型.md §2.4-2.5）。

群组拥有一个自动创建的协调者 Agent（coordinator_id）与一组人选成员
（member_ids，不含协调者）。名称格式校验在 L4（Pydantic），此处只保证非空。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.exceptions import DomainError
from app.domain.enums import DispatchMode


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Group:
    """群组聚合根。coordinator_config 为按群模型/参数覆盖（M3 用），创建时不暴露。

    群级 dispatch_mode 暂存 coordinator_config['dispatch_mode']（默认 DISCUSSION），
    v4 R2 后降级为软偏好，不作为路由分支条件。
    """

    name: str
    coordinator_id: UUID
    description: str = ""
    member_ids: list[UUID] = field(default_factory=list)
    coordinator_config: dict = field(default_factory=dict)
    workspace_path: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainError("Group name 不能为空")

    @property
    def dispatch_mode(self) -> DispatchMode:
        raw = self.coordinator_config.get("dispatch_mode")
        if raw is None:
            return DispatchMode.DISCUSSION
        try:
            return DispatchMode(raw)
        except ValueError:
            return DispatchMode.AT_ROUTING

    def set_dispatch_mode(self, mode: DispatchMode) -> None:
        self.coordinator_config["dispatch_mode"] = mode.value
        self.updated_at = _now()
