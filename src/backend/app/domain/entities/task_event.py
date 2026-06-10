"""TaskEvent：任务编排的只追加事件（AR-05 事件溯源）。

board Task（UUID）是事件的归属键；引擎内部 TaskDef 的 str id 落在 event_data.node。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class TaskEvent:
    task_id: UUID
    event_type: str
    id: UUID = field(default_factory=uuid4)
    event_data: dict = field(default_factory=dict)
    actor: str = "system"
    created_at: datetime = field(default_factory=_now)
