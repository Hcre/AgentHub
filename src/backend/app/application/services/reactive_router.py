"""ReactiveRouter — v4 统一前门路由（design §4「一扇门，一条路」）。

群聊层只有「转发」：decide 一次轻 LLM（tool_use）从**四个动作**里出一个——

    relay(who) / task / replan / done

- `relay(who)`：把这条消息转给某些成员。**投递怎么送达由投递层按目标状态定**
  （空闲→群聊回话 / 在跑→进桶 turn-end 注入 / 停了→续上下文 resume）——
  路由器不判 feed/note/respond，只决定「转给谁」。respond/multi/feed/note 全塌进这里。
- `task`：新开发任务 → Planner 建 DAG → 后台 Harness。
- `replan`：改当前任务的根本方向 → Planner 改图 → diff → 破坏性才确认。
- `done`：不需要任何响应，静默。

`active_plan` 和 `dispatch_mode` 都只是 decide 读的**输入字段**（§2.3 零模式），不是分支条件。
机械反射（@mention / control / broadcast / replan 确认）已在 ChatService 前门拦截，不进这里。

可测接缝：`_parse_payload` 纯函数。降级铁律：任何异常/不可解析 → `done`（静默，不阻塞用户）。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

import anthropic
from openai import AsyncOpenAI

from app.application.services.session_state import SessionState
from app.core.config import settings
from app.domain.enums import MessageRole

logger = logging.getLogger(__name__)

Action = Literal["relay", "task", "replan", "done"]


@dataclass(frozen=True)
class PlannerDecision:
    """reactive 决策结果。

    who=relay 的目标成员名（一个或多个）；requirement=replan 的新需求文本。
    relay 的消息文本由调用方取原始消息，不在此 DTO 里。
    """

    action: Action
    who: tuple[str, ...] = field(default_factory=tuple)
    requirement: str | None = None  # replan 用
    reason: str = ""  # 可观测

    @classmethod
    def done(cls, reason: str = "") -> PlannerDecision:
        return cls(action="done", reason=reason)


# LLM 原始决策接缝：返回 tool_use 载荷 dict（{action, who, requirement, reason}）。
# 注入 fake 即可单测 decide 的解析/降级，不碰真 SDK。
RawDecideFn = Callable[[SessionState], Awaitable[dict]]

_MAX_TRANSCRIPT = 15
_PER_MSG_CHARS = 300


class ReactiveRouter:
    """统一前门 reactive 决策器。无状态，每次读 SessionState；走廉价模型 tool_use。"""

    def __init__(
        self,
        *,
        raw_decide: RawDecideFn | None = None,  # 测试注入；None → 真 LLM
        client: anthropic.AsyncAnthropic | AsyncOpenAI | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._raw_decide = raw_decide
        self._client = client
        self._model = model or settings.reactive_model
        self._provider = provider or settings.reactive_provider

    async def decide(self, state: SessionState) -> PlannerDecision:
        """一次 reactive 决策。异常/畸形 → done（降级，不阻塞）。"""
        try:
            payload = await (
                self._raw_decide(state) if self._raw_decide is not None
                else self._llm_raw_decide(state)
            )
        except Exception as exc:
            logger.warning("ReactiveRouter LLM 失败，降级 done: %s", exc)
            return PlannerDecision.done(f"llm error: {exc.__class__.__name__}")
        decision = self._parse_payload(payload, state)
        logger.info(
            "LLM decide: action=%s who=%s reason=%s payload=%s",
            decision.action, decision.who, decision.reason, payload,
        )
        return decision

    # --- 纯解析（可直接单测）---

    @staticmethod
    def _parse_payload(payload: dict, state: SessionState) -> PlannerDecision:
        action = payload.get("action")
        reason = payload.get("reason", "")
        member_names = {a.name for a in state.members}

        if action == "relay":
            raw_who = payload.get("who") or []
            if isinstance(raw_who, str):  # 容错：LLM 偶尔吐字符串而非数组
                raw_who = [raw_who]
            who = tuple(n for n in raw_who if n in member_names)
            if not who:
                logger.warning("ReactiveRouter relay 无有效 who（原始=%r），降级 done", raw_who)
                return PlannerDecision.done("relay: no valid who")
            return PlannerDecision(action="relay", who=who, reason=reason)

        if action == "task":
            return PlannerDecision(action="task", reason=reason)

        if action == "replan":
            requirement = payload.get("requirement") or reason
            if not requirement:
                logger.warning("ReactiveRouter replan 无 requirement，降级 done")
                return PlannerDecision.done("replan: no requirement")
            return PlannerDecision(action="replan", requirement=requirement, reason=reason)

        if action == "done":
            return PlannerDecision.done(reason)

        logger.warning("ReactiveRouter 非法 action=%r，降级 done", action)
        return PlannerDecision.done(f"invalid action: {action}")

    # --- 真 LLM 路径（provider 分发，复用 selector 的 tool_use 范式）---

    @staticmethod
    def _tool_schema() -> dict:
        return {
            "name": "route_message",
            "description": "对群聊最后一条消息做路由决策",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["relay", "task", "replan", "done"],
                        "description": (
                            "relay=把这条转给某些成员（闲聊回话/接话/补充约束都算）；"
                            "task=复杂多步骤任务，需后台编排（单步骤操作请用 relay）；"
                            "replan=改变当前正在跑的任务的根本方向/架构/需求；"
                            "done=无需任何响应"
                        ),
                    },
                    "who": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "relay 时填目标成员 name（每项必须是候选成员）",
                    },
                    "requirement": {
                        "type": "string",
                        "description": "replan 时填，用户要求的新方向/需求原文",
                    },
                    "reason": {"type": "string"},
                },
                "required": ["action"],
            },
        }

    def _build_prompts(self, state: SessionState) -> tuple[str, str]:
        members = "\n".join(
            f"- {a.name}（角色：{a.role or '未指定'}；能力：{', '.join(a.capability_tags) or '通用'}）"
            for a in state.members
        )
        # active_plan：有任务在跑就把各 step 状态摆出来（供判断转给谁/是否 replan），没有就说明纯对话。
        if state.active_plan and state.active_plan.steps:
            plan_ctx = "## 任务在跑，各 step 状态：\n" + "\n".join(
                f"- {s.step_id}（{s.worker}）：{s.status}" for s in state.active_plan.steps
            )
        else:
            plan_ctx = "## 当前没有任务在跑（纯对话）"

        guide = (
            "## 决策流程：先判类型，再选人\n\n"
            "### 🔍 第一步：判断消息应该怎么处理\n\n"
            "**task — 复杂多步骤任务，需要后台编排**\n"
            "同时满足以下条件时判 task：\n"
            "1. 用户要求产出实质性成果（报告、系统、功能模块、调研分析等）\n"
            "2. 任务涉及 ≥2 个不同性质的工作步骤（如：先调研再写、先设计再实现、先分析再汇总）\n"
            "3. 单一个人难以独立完成，需要分工协作\n"
            "典型示例：「写调研报告」「开发一个功能」「分析数据并输出报告」「搭建系统」「做一个项目」\n"
            "注意：单步骤操作（新建文件、查资料、改一行配置）不算 task。\n"
            "判 task 后无需指定 who，编排系统会自动分配。\n\n"
            "**replan — 改变当前任务方向**\n"
            "有任务在跑，用户要求改根本方向/架构（如「改成微服务」「不做博客了做文档站」）。\n\n"
            "**done — 不需要响应**\n"
            "以下情况必须 done：\n"
            "- Agent 已完成指令给出结果，等用户下一步\n"
            "- Agent 在追问用户确认细节，等用户回复\n"
            "- 状态汇报/确认类消息，无需继续传递\n"
            "- 上一轮已完成用户要求，没有新问题需要解决\n\n"
            "**relay — 转给成员执行/回复**\n"
            "以上都不满足时走 relay。包括：闲聊回复、简单执行指令（创建文件/改配置/查资料）、补充信息、接话讨论等。\n\n"
            "### 🎯 第二步：如果是 relay，选谁\n"
            "- 根据消息内容和成员角色/能力匹配最合适的人\n"
            "- 单一领域问题 → 选最合适的一人即可\n"
            "- 跨领域/涉及多方 → 可以选多个相关成员（根据实际需要，不强制）\n"
            "- 不用区分对方在回话还是干活，只管转给最该接的人\n\n"
            "### ⚠️ 常见误判提醒\n"
            "- 不要把复杂的多步骤任务漏判成 relay（如「写调研报告」→ task，不是 relay）\n"
            "- 不要因为消息含技术词就自动判 task\n"
            "- 判断依据是「任务复杂度 + 步骤数量 + 是否需要协作」，不是「消息里有没有技术词汇」"
        )
        system = (
            "# 角色\n"
            "你是 AgentHub 群聊的路由器。只对「待路由消息」做一次决策，历史上下文仅供理解背景。\n\n"
            + plan_ctx + "\n\n"
            + guide
        )

        id_to_name = {a.id: a.name for a in state.members}
        transcript = list(state.transcript)

        def _fmt(m: Message) -> str:
            if m.created_at:
                local = m.created_at.astimezone()
                ts = local.strftime("%H:%M:%S")
            else:
                ts = "--:--:--"
            if m.role == MessageRole.SYSTEM:
                who = "系统"
            elif m.sender_agent_id is None:
                who = "用户"
            else:
                who = id_to_name.get(m.sender_agent_id, "某成员")
            content = (m.content or "")[:_PER_MSG_CHARS]
            return f"[{ts}] {who}: {content}"

        if not transcript:
            prompt = (
                "# 候选成员\n" + members + "\n\n"
                "# 待路由消息\n（暂无）\n\n"
                "请返回 action=done。"
            )
            return system, prompt

        # transcript 为倒序（最新在前），取第一条为待路由目标，其余为历史
        target, *history = transcript
        # 过滤系统消息（噪音），只保留用户和 Agent 对话
        history = [m for m in history if m.role != MessageRole.SYSTEM][:_MAX_TRANSCRIPT]

        # 找到用户最后一条消息（从 transcript 倒序中找第一条用户消息）
        last_user = None
        for m in transcript:
            if m.sender_agent_id is None and m.role != MessageRole.SYSTEM:
                last_user = m
                break

        history_block = "\n".join(_fmt(m) for m in history) if history else "（无历史）"
        parts = [
            "# 候选成员\n" + members,
            "# 历史上下文\n（仅供理解背景，不要对这些消息做路由决策）\n" + history_block,
        ]
        if last_user and last_user.id != target.id:
            parts.append(
                "# 用户最后一条消息\n（用户的最新意图，辅助判断上下文）\n" + _fmt(last_user)
            )
        parts.append(
            "# 待路由消息\n" + _fmt(target) + "\n\n请通过 route_message 返回决策。"
        )
        prompt = "\n\n".join(parts)
        logger.info("ReactiveRouter prompt:\n--- system ---\n%s\n--- user ---\n%s", system, prompt)
        return system, prompt

    async def _llm_raw_decide(self, state: SessionState) -> dict:
        if self._provider == "anthropic":
            return await self._raw_anthropic(state)
        return await self._raw_openai(state)

    async def _raw_anthropic(self, state: SessionState) -> dict:
        client = (
            self._client
            if isinstance(self._client, anthropic.AsyncAnthropic)
            else anthropic.AsyncAnthropic()
        )
        system, prompt = self._build_prompts(state)
        resp = await client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[self._tool_schema()],
            tool_choice={"type": "tool", "name": "route_message"},
        )
        tool_use = next((b for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
        if tool_use is None:
            raise ValueError("anthropic 未返回 tool_use")
        return dict(tool_use.input or {})

    async def _raw_openai(self, state: SessionState) -> dict:
        import json as _json

        if isinstance(self._client, AsyncOpenAI):
            client = self._client
        elif self._provider == "deepseek":
            client = AsyncOpenAI(base_url="https://api.deepseek.com/v1", api_key=settings.deepseek_api_key)
        else:
            client = AsyncOpenAI(api_key=settings.openai_api_key)
        system, prompt = self._build_prompts(state)
        ant = self._tool_schema()
        extra = {}
        if self._provider == "deepseek":
            extra["extra_body"] = {"thinking": {"type": "disabled"}}
        resp = await client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            tools=[{"type": "function", "function": {
                "name": ant["name"], "description": ant["description"], "parameters": ant["input_schema"],
            }}],
            tool_choice={"type": "function", "function": {"name": "route_message"}},
            max_tokens=512,
            **extra,
        )
        tcs = resp.choices[0].message.tool_calls
        if not tcs:
            raise ValueError("openai 未返回 tool_calls")
        return _json.loads(tcs[0].function.arguments)
