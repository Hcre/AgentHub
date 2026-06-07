"""PostgresUsageRepository（P1-2）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.usage import UsageRecord, UsageWindow
from app.domain.usage.usage_record import (
    USAGE_KIND_COMPLETION,
    USAGE_KIND_PROMPT,
)
from app.infrastructure.db.models import UsageRecordModel


def _to_domain(m: UsageRecordModel) -> UsageRecord:
    return UsageRecord(
        id=m.id,
        agent_id=m.agent_id,
        session_id=m.session_id,
        message_id=m.message_id,
        kind=m.kind,
        tokens=m.tokens,
        model=m.model,
        created_at=m.created_at,
    )


class PostgresUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, record: UsageRecord) -> None:
        self._s.add(
            UsageRecordModel(
                id=record.id,
                agent_id=record.agent_id,
                session_id=record.session_id,
                message_id=record.message_id,
                kind=record.kind,
                tokens=record.tokens,
                model=record.model,
                created_at=record.created_at,
            )
        )
        await self._s.flush()

    async def _bucket_sum(self, *, where_clauses: list) -> dict[str, int]:
        stmt = (
            select(
                UsageRecordModel.kind,
                func.coalesce(func.sum(UsageRecordModel.tokens), 0),
            )
            .where(*where_clauses)
            .group_by(UsageRecordModel.kind)
        )
        rows = (await self._s.execute(stmt)).all()
        prompt = completion = 0
        for kind, total in rows:
            if kind == USAGE_KIND_PROMPT:
                prompt = int(total)
            elif kind == USAGE_KIND_COMPLETION:
                completion = int(total)
        return {"prompt": prompt, "completion": completion, "total": prompt + completion}

    async def sum_by_agent(self, agent_id: UUID, window: UsageWindow) -> dict[str, int]:
        return await self._bucket_sum(
            where_clauses=[
                UsageRecordModel.agent_id == agent_id,
                UsageRecordModel.created_at >= window.since,
            ]
        )

    async def sum_by_session(self, session_id: UUID, window: UsageWindow) -> dict[str, int]:
        return await self._bucket_sum(
            where_clauses=[
                UsageRecordModel.session_id == session_id,
                UsageRecordModel.created_at >= window.since,
            ]
        )

    async def group_by_session(self, agent_id: UUID, window: UsageWindow) -> list[dict]:
        stmt = (
            select(
                UsageRecordModel.session_id,
                UsageRecordModel.kind,
                func.coalesce(func.sum(UsageRecordModel.tokens), 0),
                func.count(UsageRecordModel.message_id.distinct()),
            )
            .where(
                UsageRecordModel.agent_id == agent_id,
                UsageRecordModel.created_at >= window.since,
            )
            .group_by(UsageRecordModel.session_id, UsageRecordModel.kind)
        )
        rows = (await self._s.execute(stmt)).all()
        agg: dict[UUID, dict] = {}
        for sid, kind, total, msg_count in rows:
            bucket = agg.setdefault(
                sid,
                {
                    "session_id": str(sid),
                    "prompt": 0,
                    "completion": 0,
                    "total": 0,
                    "msg_count": 0,
                },
            )
            if kind == USAGE_KIND_PROMPT:
                bucket["prompt"] = int(total)
            elif kind == USAGE_KIND_COMPLETION:
                bucket["completion"] = int(total)
                bucket["msg_count"] = int(msg_count)
        for b in agg.values():
            b["total"] = b["prompt"] + b["completion"]
        return sorted(agg.values(), key=lambda x: x["total"], reverse=True)

    async def group_by_agent(self, session_id: UUID, window: UsageWindow) -> list[dict]:
        stmt = (
            select(
                UsageRecordModel.agent_id,
                UsageRecordModel.kind,
                func.coalesce(func.sum(UsageRecordModel.tokens), 0),
            )
            .where(
                UsageRecordModel.session_id == session_id,
                UsageRecordModel.created_at >= window.since,
            )
            .group_by(UsageRecordModel.agent_id, UsageRecordModel.kind)
        )
        rows = (await self._s.execute(stmt)).all()
        agg: dict[UUID, dict] = {}
        for aid, kind, total in rows:
            if aid is None:
                continue
            bucket = agg.setdefault(
                aid,
                {"agent_id": str(aid), "prompt": 0, "completion": 0, "total": 0},
            )
            if kind == USAGE_KIND_PROMPT:
                bucket["prompt"] = int(total)
            elif kind == USAGE_KIND_COMPLETION:
                bucket["completion"] = int(total)
        for b in agg.values():
            b["total"] = b["prompt"] + b["completion"]
        return sorted(agg.values(), key=lambda x: x["total"], reverse=True)
