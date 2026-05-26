"""ContextBuilder：群聊 Agent 上下文增量注入。

设计依据：docs/design/group-chat_群聊功能设计方案.md §3.4 增量注入方案。

核心：Watermark 跟踪每 Agent「上次接触到第几条消息」，每次只注入 delta。
私聊场景退化为「最近 L1 窗口全量注入」，保持向后兼容。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.application.services.prompt_templates import (
    GROUP_CHAT_CONTRACT,
    format_delta,
    format_members,
)
from app.core.config import settings
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.llm.protocol import AgentRequest, MemoryContext
from app.domain.repositories import AgentRepository, MessageRepository
from app.infrastructure.cache.memory_l1 import L1MemoryStore
from app.infrastructure.cache.watermark_store import WatermarkStore

logger = logging.getLogger(__name__)


@dataclass
class _DeltaResult:
    messages: list[Message]
    truncated_count: int  # 被截断的更早消息数量（>0 表示已截断）


class ContextBuilder:
    """群聊场景 AgentRequest 装配器（增量注入）。"""

    def __init__(
        self,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        l1_memory: L1MemoryStore,
        watermarks: WatermarkStore,
    ) -> None:
        self._messages = message_repo
        self._agents = agent_repo
        self._l1 = l1_memory
        self._wm = watermarks

    async def build_for_agent(
        self,
        *,
        session: Session,
        group: Group | None,
        target_agent: Agent,
        trigger: Message,
    ) -> AgentRequest:
        """组装 Agent 的 AgentRequest。

        - 群聊：注入 GROUP_CHAT_CONTRACT + 成员列表 + delta 增量
        - 私聊：注入 Agent 自身 system_prompt + 完整 L1 窗口（向后兼容）
        """
        if group is not None:
            return await self._build_group(
                session=session,
                group=group,
                target_agent=target_agent,
                trigger=trigger,
            )
        return await self._build_private(
            session=session, target_agent=target_agent, trigger=trigger
        )

    # --- 群聊路径 ---

    async def _build_group(
        self,
        *,
        session: Session,
        group: Group,
        target_agent: Agent,
        trigger: Message,
    ) -> AgentRequest:
        # 1. 算 delta
        delta = await self._compute_delta(
            session_id=session.id, group_id=group.id, agent_id=target_agent.id
        )

        # 2. 渲染成员列表
        members = await self._load_members(group)
        members_block = format_members(members, target_agent)

        # 3. 拼 stable_prefix（cache 友好）
        persona = target_agent.system_prompt or f"你是 {target_agent.name}。"
        agent_name_by_id = {m.id: m.name for m in members}
        delta_block = format_delta(delta.messages, agent_name_by_id)
        truncated_hint = (
            f"\n[省略了更早的 {delta.truncated_count} 条群聊消息]\n"
            if delta.truncated_count > 0
            else ""
        )

        system_prompt = "\n\n".join(
            filter(
                None,
                [
                    persona,
                    GROUP_CHAT_CONTRACT,
                    members_block,
                    truncated_hint + delta_block if delta_block else None,
                ],
            )
        )

        # 4. L1 窗口仅作为辅助记忆传递（CLI Runtime 实际只用 system_prompt + 最后一条 user）
        window = await self._l1.get_window(session.id)

        return AgentRequest(
            request_id=str(uuid.uuid4()),
            session_id=session.id,
            messages=[{"role": "user", "content": trigger.content}],
            system_prompt=system_prompt,
            memory=MemoryContext(l1_working=window),
            max_tokens=settings.max_tokens,
            agent_id=target_agent.id,
            group_id=group.id,
            is_group_chat=True,
        )

    # --- 私聊路径（向后兼容 MVP 行为） ---

    async def _build_private(
        self,
        *,
        session: Session,
        target_agent: Agent,
        trigger: Message,
    ) -> AgentRequest:
        window = await self._l1.get_window(session.id)
        return AgentRequest(
            request_id=str(uuid.uuid4()),
            session_id=session.id,
            messages=window,
            system_prompt=target_agent.system_prompt,
            memory=MemoryContext(l1_working=window),
            max_tokens=settings.max_tokens,
            agent_id=target_agent.id,
            is_group_chat=False,
        )

    # --- delta 计算 ---

    async def _compute_delta(
        self, *, session_id: uuid.UUID, group_id: uuid.UUID, agent_id: uuid.UUID
    ) -> _DeltaResult:
        wm = await self._wm.get(group_id, agent_id)
        if wm is None:
            # 首次接触：给一段种子历史
            seed = await self._messages.list_by_session(
                session_id, limit=settings.l1_window_size
            )
            return self._maybe_truncate(seed)

        # 优先走 L1 cache
        window = await self._l1.get_window(session_id)
        delta_from_l1 = self._extract_delta_from_l1(window, wm)
        if delta_from_l1 is not None:
            return self._maybe_truncate(delta_from_l1)

        # L1 不够（沉默太久），回 PG
        delta = await self._messages.list_after(
            session_id, wm, limit=settings.max_delta_messages + 1
        )
        if not delta:
            # 水位点已被删除或不存在 → 退化为首次接触
            logger.warning(
                "watermark %s 在 PG 不存在，退化为首次接触种子历史 session=%s agent=%s",
                wm,
                session_id,
                agent_id,
            )
            seed = await self._messages.list_by_session(
                session_id, limit=settings.l1_window_size
            )
            return self._maybe_truncate(seed)
        return self._maybe_truncate(delta)

    @staticmethod
    def _extract_delta_from_l1(
        window: list[dict], wm: uuid.UUID
    ) -> list[Message] | None:
        """L1 当前以 role/content 字典存储，未带 message_id，暂无法从 L1 过滤 → 走 PG。

        预留接口：未来 L1 改成 List[Message dict with id] 后启用快路径。
        """
        return None

    @staticmethod
    def _maybe_truncate(msgs: list[Message]) -> _DeltaResult:
        max_n = settings.max_delta_messages
        if len(msgs) <= max_n:
            return _DeltaResult(messages=msgs, truncated_count=0)
        truncated = len(msgs) - max_n
        return _DeltaResult(messages=msgs[-max_n:], truncated_count=truncated)

    # --- 成员加载 ---

    async def _load_members(self, group: Group) -> list[Agent]:
        ids = list({*group.member_ids, group.coordinator_id})
        members: list[Agent] = []
        for aid in ids:
            agent = await self._agents.get_by_id(aid)
            if agent is not None:
                members.append(agent)
        return members
