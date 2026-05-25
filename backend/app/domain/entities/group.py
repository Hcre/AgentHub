"""Group 聚合根（spec/data-model §2.4-2.5）。

群组拥有一个自动创建的协调者 Agent（coordinator_id）与一组人选成员
（member_ids，不含协调者）。名称格式校验在 L4（Pydantic），此处只保证非空。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.exceptions import DomainError


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Group:
    """群组聚合根。coordinator_config 为按群模型/参数覆盖（M3 用），创建时不暴露。"""

    name: str
    coordinator_id: UUID
    description: str = ""
    member_ids: list[UUID] = field(default_factory=list)
    coordinator_config: dict = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainError("Group name 不能为空")
