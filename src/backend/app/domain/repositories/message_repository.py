"""MessageRepository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.message import Message


class MessageRepository(ABC):
    @abstractmethod
    async def save(self, message: Message) -> None: ...

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Message | None: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: UUID, *, before: UUID | None = None, limit: int = 50
    ) -> list[Message]:
        """按时间倒序分页拉取会话历史。"""
        ...

    @abstractmethod
    async def list_after(
        self, session_id: UUID, after_message_id: UUID, *, limit: int = 100
    ) -> list[Message]:
        """拉取 after_message_id 之后的消息（正序，含尾部）。

        群聊增量注入用（docs/design/group-chat_群聊功能设计方案.md §3.4）。
        若 after_message_id 不存在，返回空列表（调用方应回退到首次接触路径）。
        """
        ...

    @abstractmethod
    async def has_assistant_messages(
        self, session_id: UUID, *, sender_agent_id: UUID | None = None
    ) -> bool:
        """是否已有 assistant 消息（用于判断 CLI --resume vs --session-id）。

        sender_agent_id 为空时按 session 级判断；非空时仅统计该 Agent 发出的
        assistant 消息。群聊里 CLI session_key 是 per-agent（uuid5），磁盘历史也
        按 agent 隔离，故必须按 agent 过滤——否则别的 Agent 先回复就会误判本
        Agent 有历史，触发对不存在 session 的 --resume（会 fallback 甚至撞锁僵死）。
        """
        ...

    @abstractmethod
    async def set_pinned(
        self,
        message_id: UUID,
        pinned: bool,
        *,
        pinned_by_user_id: UUID | None = None,
    ) -> None:
        """切换 pinned 状态。pinned=True 时记录 pinned_by_user_id + pinned_at，False 时清空。"""
        ...

    @abstractmethod
    async def delete(self, message_id: UUID) -> None: ...
