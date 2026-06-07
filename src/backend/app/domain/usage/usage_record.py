"""Token 消耗明细实体（P1-2 / spec 04-commands §6.6）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

USAGE_KIND_PROMPT = "prompt"
USAGE_KIND_COMPLETION = "completion"
USAGE_KIND_TOTAL = "total"

_VALID_WINDOWS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


@dataclass
class UsageRecord:
    """一条 token 消耗记录（append-only 日志行）。"""

    session_id: UUID
    kind: str
    tokens: int
    id: UUID = field(default_factory=uuid4)
    agent_id: UUID | None = None
    message_id: UUID | None = None
    model: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class UsageWindow:
    name: str
    since: datetime

    @classmethod
    def from_name(cls, name: str, *, now: datetime | None = None) -> UsageWindow:
        if name not in _VALID_WINDOWS:
            raise ValueError(f"window must be one of 1h/24h/7d, got {name!r}")
        anchor = now or datetime.now(UTC)
        return cls(name=name, since=anchor - _VALID_WINDOWS[name])
