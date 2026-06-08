"""UsageService（L3）：Token 消耗监控（P1-2）。"""

from __future__ import annotations

import logging
from uuid import UUID

from app.domain.repositories import UsageRepository
from app.domain.usage import TokenCounter, UsageRecord, UsageWindow

logger = logging.getLogger(__name__)


class UsageService:
    def __init__(
        self,
        usage_repo: UsageRepository,
        *,
        counter: TokenCounter | None = None,
    ) -> None:
        self._repo = usage_repo
        self._counter = counter or TokenCounter()

    async def record(self, record: UsageRecord) -> None:
        await self._repo.save(record)

    async def record_completion(
        self,
        *,
        session_id: UUID,
        message_id: UUID,
        agent_id: UUID,
        content: str,
        metadata: dict | None,
        model: str | None,
    ) -> list[UsageRecord]:
        records = self._counter.count_completion(
            session_id=session_id,
            message_id=message_id,
            agent_id=agent_id,
            content=content,
            metadata=metadata,
            model=model,
        )
        for r in records:
            await self._repo.save(r)
        return records

    async def record_user_message(
        self, *, session_id: UUID, message_id: UUID, content: str
    ) -> list[UsageRecord]:
        records = self._counter.count_user_message(
            session_id=session_id, message_id=message_id, content=content
        )
        for r in records:
            await self._repo.save(r)
        return records

    async def aggregate_by_agent(self, agent_id: UUID, window_name: str = "24h") -> dict:
        window = UsageWindow.from_name(window_name)
        total = await self._repo.sum_by_agent(agent_id, window)
        by_session = await self._repo.group_by_session(agent_id, window)
        return {
            "agent_id": str(agent_id),
            "window": window_name,
            "since": window.since.isoformat(),
            "prompt_tokens": total["prompt"],
            "completion_tokens": total["completion"],
            "total_tokens": total["total"],
            "by_session": by_session,
        }

    async def aggregate_by_session(self, session_id: UUID, window_name: str = "24h") -> dict:
        window = UsageWindow.from_name(window_name)
        total = await self._repo.sum_by_session(session_id, window)
        by_agent = await self._repo.group_by_agent(session_id, window)
        return {
            "session_id": str(session_id),
            "window": window_name,
            "since": window.since.isoformat(),
            "prompt_tokens": total["prompt"],
            "completion_tokens": total["completion"],
            "total_tokens": total["total"],
            "by_agent": by_agent,
        }

    async def aggregate_global(self, window_name: str = "24h", top_n: int = 10) -> dict:
        """全平台 Token 聚合（t6 Token 监控 UI 用，不限 agent/session）。"""
        window = UsageWindow.from_name(window_name)
        total = await self._repo.sum_global(window)
        by_agent = await self._repo.group_by_agent_global(window, top_n=top_n)
        return {
            "window": window_name,
            "since": window.since.isoformat(),
            "prompt_tokens": total["prompt"],
            "completion_tokens": total["completion"],
            "total_tokens": total["total"],
            "by_agent": by_agent,
        }
