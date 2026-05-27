"""Selector：群聊讨论模式的「下一位发言人」程序驱动决策器。

设计依据：
- docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md §6.2 分层路由
- docs/design/group-chat-discussion-mode_群聊讨论模式设计方案.md §6.3 防循环
- docs/design/group-chat-implementation-plan_群聊实施计划.md Phase 5

四层路由：
1. @mention 直达（含 Agent 自治 @ 接力，Bypass，零 LLM）
1.5 全体意图硬编码拦截（零 LLM，keyword → picks=全成员）
2. capability_tags 关键词匹配（零 LLM）
3. LLM 决策（Anthropic/DeepSeek tool_use，支持 next/multi/done 三种 decision）

失败降级：任何异常 / 不可解析 → done=True（不阻塞用户）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

import anthropic
from openai import AsyncOpenAI

from app.core.config import settings
from app.domain.entities.agent import Agent
from app.domain.entities.message import Message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectorDecision:
    next_agent_id: UUID | None
    done: bool
    reason: str = ""  # 调试/可观测
    mention_queue: tuple[UUID, ...] = ()  # 剩余待处理的 @mention
    picks: tuple[UUID, ...] = ()  # 同回合多人响应；非空时 DiscussionOrchestrator 并行执行

    @classmethod
    def pick(
        cls, agent_id: UUID, reason: str = "", mention_queue: tuple[UUID, ...] = ()
    ) -> SelectorDecision:
        return cls(
            next_agent_id=agent_id, done=False, reason=reason, mention_queue=mention_queue
        )

    @classmethod
    def pick_multi(
        cls, agent_ids: tuple[UUID, ...], reason: str = ""
    ) -> SelectorDecision:
        return cls(next_agent_id=None, done=False, reason=reason, picks=agent_ids)

    @classmethod
    def finish(cls, reason: str = "") -> SelectorDecision:
        return cls(next_agent_id=None, done=True, reason=reason)


_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_一-龥\-]+)")
_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")
_PER_MESSAGE_CHAR_LIMIT = 300

# Layer 1.5: 全体意图硬编码关键词
_BROADCAST_PATTERN = re.compile(r"大家|各位|所有人|全员|全体|在座的|你们都说说|都来说说")


class Selector:
    """讨论模式发言人决策器。

    无状态，无 CLI session；Layer 3 走 API 直调廉价模型。
    """

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | AsyncOpenAI | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client
        self._model = model or settings.selector_model
        self._provider = settings.selector_provider

    async def pick(
        self,
        *,
        members: list[Agent],
        history: list[Message],
        agent_name_by_id: dict[UUID, str] | None = None,
        already_spoken: set[UUID] | None = None,
    ) -> SelectorDecision:
        """选下一位/多位发言人或 DONE。"""
        if not members:
            return SelectorDecision.finish("members empty")
        if not history:
            return SelectorDecision.finish("history empty")

        name_by_id = agent_name_by_id or {a.id: a.name for a in members}
        last = history[-1]

        # Layer 1: @mention 直达
        mention_decision = self._resolve_mention(last, members)
        if mention_decision is not None:
            return mention_decision

        # Layer 1.5: 全体意图硬编码拦截
        broadcast_decision = self._resolve_broadcast(last, members)
        if broadcast_decision is not None:
            return broadcast_decision

        # Layer 2: capability_tags 关键词匹配
        kw_decision = self._resolve_keyword(last, members)
        if kw_decision is not None:
            return kw_decision

        # Layer 3: LLM 决策
        return await self._llm_decide(
            members=members,
            history=history,
            name_by_id=name_by_id,
            already_spoken=already_spoken or set(),
        )

    # --- Layer 1 ---

    @staticmethod
    def _resolve_mention(
        last: Message, members: list[Agent]
    ) -> SelectorDecision | None:
        member_by_name = {a.name: a for a in members}
        collected: list[UUID] = []

        if last.mentions:
            for name in last.mentions:
                hit = member_by_name.get(name)
                if hit is not None:
                    collected.append(hit.id)

        content = last.content or ""
        for match in _MENTION_PATTERN.finditer(content):
            name = match.group(1)
            hit = member_by_name.get(name)
            if (
                hit is not None
                and hit.id != last.sender_agent_id
                and hit.id not in collected
            ):
                collected.append(hit.id)

        if not collected:
            return None

        first, *rest = collected
        return SelectorDecision.pick(
            first, reason=f"@mention={first}", mention_queue=tuple(rest)
        )

    # --- Layer 1.5: 全体意图硬编码 ---

    @staticmethod
    def _resolve_broadcast(
        last: Message, members: list[Agent]
    ) -> SelectorDecision | None:
        """检测用户是否在呼叫全体成员。

        规则：消息含「大家/各位/所有人」等全体关键词 →
        返回 pick_multi(全体成员)，LLM 不参与。

        注意：仅对用户消息生效，Agent 消息不触发（避免 Agent
        说了「大家好」后连锁全体响应）。
        """
        if last.sender_agent_id is not None:
            return None  # 非用户消息，跳过
        content = last.content or ""
        if not _BROADCAST_PATTERN.search(content):
            return None
        agent_ids = tuple(a.id for a in members if a.id != last.sender_agent_id)
        if not agent_ids:
            return None
        logger.info("Selector Layer1.5 全体意图触发，pick_multi=%d agents", len(agent_ids))
        return SelectorDecision.pick_multi(agent_ids, reason="broadcast keyword")

    # --- Layer 2 ---

    @staticmethod
    def _resolve_keyword(
        last: Message, members: list[Agent]
    ) -> SelectorDecision | None:
        content = (last.content or "").lower()
        if not content.strip():
            return None
        best: tuple[Agent, int] | None = None
        for agent in members:
            if agent.id == last.sender_agent_id:
                continue
            hit_count = sum(
                1 for tag in agent.capability_tags if tag and tag.lower() in content
            )
            if hit_count > 0 and (best is None or hit_count > best[1]):
                best = (agent, hit_count)
        if best is not None:
            return SelectorDecision.pick(
                best[0].id, reason=f"capability hit={best[1]}"
            )
        return None

    # --- Layer 3 ---

    async def _llm_decide(
        self,
        *,
        members: list[Agent],
        history: list[Message],
        name_by_id: dict[UUID, str],
        already_spoken: set[UUID],
    ) -> SelectorDecision:
        candidates = [a for a in members if a.id not in already_spoken]
        if not candidates:
            return SelectorDecision.finish("all spoken in this round")

        if self._provider == "anthropic":
            return await self._llm_decide_anthropic(
                candidates=candidates, history=history, name_by_id=name_by_id
            )
        return await self._llm_decide_openai(
            candidates=candidates, history=history, name_by_id=name_by_id
        )

    @staticmethod
    def _build_prompts(
        *,
        candidates: list[Agent],
        history: list[Message],
        name_by_id: dict[UUID, str],
    ) -> tuple[str, str]:
        system = (
            "你是多 Agent 群聊的发言调度器。基于群聊记录判断下一位或多位最应该发言的成员，"
            "或宣告讨论已收敛。\n\n"
            "判断规则：\n"
            "1. 如果讨论已自然结束、无新信息可贡献 → decision=done\n"
            "2. 如果某成员的能力与当前话题强相关 → decision=next, agent_name=该成员\n"
            "3. 如果用户向全体提问（「大家怎么看」「各位有什么建议」），"
            "需要多个人从不同角度回应 → decision=multi, agent_names=所有相关成员\n"
            "4. 如果讨论在重复已有观点 → decision=done\n"
            "5. 不选已发言成员（除非有强烈理由）\n"
            "6. 必须通过 select_next_speaker 工具返回决策"
        )

        cand_lines = [
            f"- {a.name}（角色：{a.role or '未指定'}；能力：{', '.join(a.capability_tags) or '通用'}）"
            for a in candidates
        ]
        cand_block = "\n".join(cand_lines)

        hist_lines: list[str] = []
        for msg in history[-15:]:
            speaker = (
                name_by_id.get(msg.sender_agent_id, "未知 Agent")
                if msg.sender_agent_id
                else "用户"
            )
            content = msg.content or ""
            content = _CODE_BLOCK_PATTERN.sub("[代码片段已省略]", content)
            if len(content) > _PER_MESSAGE_CHAR_LIMIT:
                content = content[:_PER_MESSAGE_CHAR_LIMIT] + "..."
            hist_lines.append(f"{speaker}: {content}")

        prefix = "候选成员：\n" + cand_block + "\n\n群聊记录（按时间顺序）：\n---\n"
        suffix = "\n---\n\n请通过 select_next_speaker 工具返回决策。"

        max_chars = settings.selector_max_prompt_chars
        overhead = len(system) + len(prefix) + len(suffix)
        budget = max(100, max_chars - overhead)
        trimmed = list(hist_lines)
        while trimmed:
            body = "\n".join(trimmed)
            if len(body) <= budget:
                break
            if len(trimmed) == 1:
                trimmed[0] = trimmed[0][: budget - 3] + "..."
                break
            trimmed.pop(0)

        prompt = prefix + "\n".join(trimmed) + suffix
        return system, prompt

    @staticmethod
    def _tool_schema() -> dict[str, object]:
        """返回 Anthropic 格式 tool schema（OpenAI 路径使用时转换）。"""
        return {
            "name": "select_next_speaker",
            "description": "选定下一位或多位发言人，或宣告讨论收敛",
            "input_schema": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["next", "multi", "done"],
                        "description": (
                            "next=选一人发言；multi=选多人同时发言（用户向全体提问时）；"
                            "done=讨论已收敛"
                        ),
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "decision=next 时填，必须是候选人之一的 name",
                    },
                    "agent_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "decision=multi 时填，每个元素必须是候选人之一的 name",
                    },
                    "reason": {"type": "string"},
                },
                "required": ["decision"],
            },
        }

    @staticmethod
    def _parse_llm_response(
        resp: anthropic.types.Message, candidates: list[Agent]
    ) -> SelectorDecision:
        tool_use = next(
            (b for b in resp.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if tool_use is None:
            logger.warning("Selector LLM 未返回 tool_use，降级 DONE")
            return SelectorDecision.finish("no tool_use")

        return Selector._parse_payload(tool_use.input or {}, candidates)

    @staticmethod
    def _parse_payload(
        payload: dict, candidates: list[Agent]
    ) -> SelectorDecision:
        decision = payload.get("decision")
        reason: str = payload.get("reason", "")

        if decision == "done":
            return SelectorDecision.finish(f"llm done: {reason}")

        if decision == "next":
            agent_name = payload.get("agent_name")
            hit = next((a for a in candidates if a.name == agent_name), None)
            if hit is None:
                logger.warning("Selector LLM 选了不存在的候选: %s，降级 DONE", agent_name)
                return SelectorDecision.finish(f"unknown candidate: {agent_name}")
            return SelectorDecision.pick(hit.id, reason=f"llm pick: {reason}")

        if decision == "multi":
            names: list[str] = payload.get("agent_names", [])
            ids: list[UUID] = []
            for name in names:
                hit = next((a for a in candidates if a.name == name), None)
                if hit is not None:
                    ids.append(hit.id)
                else:
                    logger.warning("Selector multi 选了不存在的候选: %s，跳过", name)
            if not ids:
                return SelectorDecision.finish("multi: all candidates unknown")
            logger.info("Selector LLM 返回 multi pick: %d agents", len(ids))
            return SelectorDecision.pick_multi(tuple(ids), reason=f"llm multi: {reason}")

        logger.warning("Selector LLM 返回非法 decision=%s，降级 DONE", decision)
        return SelectorDecision.finish(f"invalid decision: {decision}")

    # --- Layer 3 helpers: provider dispatch ---

    async def _llm_decide_anthropic(
        self,
        *,
        candidates: list[Agent],
        history: list[Message],
        name_by_id: dict[UUID, str],
    ) -> SelectorDecision:
        try:
            client: anthropic.AsyncAnthropic = (
                self._client
                if isinstance(self._client, anthropic.AsyncAnthropic)
                else anthropic.AsyncAnthropic()
            )
        except Exception as exc:
            logger.warning("Anthropic 客户端初始化失败，降级 DONE: %s", exc)
            return SelectorDecision.finish("anthropic init failed")

        system, prompt = self._build_prompts(
            candidates=candidates, history=history, name_by_id=name_by_id
        )
        tool = self._tool_schema()

        try:
            resp = await client.messages.create(
                model=self._model,
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool],
                tool_choice={"type": "tool", "name": "select_next_speaker"},
            )
        except Exception as exc:
            logger.warning("Selector Anthropic 调用失败，降级 DONE: %s", exc)
            return SelectorDecision.finish(f"llm error: {exc.__class__.__name__}")

        return self._parse_llm_response(resp, candidates)

    async def _llm_decide_openai(
        self,
        *,
        candidates: list[Agent],
        history: list[Message],
        name_by_id: dict[UUID, str],
    ) -> SelectorDecision:
        try:
            if self._client is not None and isinstance(self._client, AsyncOpenAI):
                client = self._client
            elif self._provider == "deepseek":
                client = AsyncOpenAI(
                    base_url="https://api.deepseek.com/v1",
                    api_key=settings.deepseek_api_key,
                )
            else:
                client = AsyncOpenAI(api_key=settings.openai_api_key)
        except Exception as exc:
            logger.warning("OpenAI 客户端初始化失败，降级 DONE: %s", exc)
            return SelectorDecision.finish("openai init failed")

        system, prompt = self._build_prompts(
            candidates=candidates, history=history, name_by_id=name_by_id
        )
        ant_tool = self._tool_schema()
        schema = ant_tool["input_schema"]
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": ant_tool["name"],
                    "description": ant_tool["description"],
                    "parameters": schema,
                },
            }
        ]

        try:
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                tools=tools,
                tool_choice={
                    "type": "function",
                    "function": {"name": "select_next_speaker"},
                },
                max_tokens=512,
            )
        except Exception as exc:
            logger.warning(
                "Selector %s 调用失败，降级 DONE: %s", self._provider, exc
            )
            return SelectorDecision.finish(f"llm error: {exc.__class__.__name__}")

        return self._parse_openai_response(resp, candidates)

    @staticmethod
    def _parse_openai_response(
        resp: object, candidates: list[Agent]
    ) -> SelectorDecision:
        import json as _json

        choice = resp.choices[0]  # type: ignore[union-attr]
        msg = choice.message
        if not msg.tool_calls:
            logger.warning("Selector OpenAI 未返回 tool_calls，降级 DONE")
            return SelectorDecision.finish("no tool_calls")

        tc = msg.tool_calls[0]
        try:
            payload = _json.loads(tc.function.arguments)
        except (_json.JSONDecodeError, AttributeError) as exc:
            logger.warning("Selector OpenAI tool_calls 参数解析失败: %s", exc)
            return SelectorDecision.finish("tool_calls parse error")

        return Selector._parse_payload(payload, candidates)
