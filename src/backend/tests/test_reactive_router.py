"""ReactiveRouter 单元测试（v4 统一路由：relay/task/replan/done 四动作）。

fake raw_decide 注入 tool 载荷，隔离真 LLM，确定性。验证 decide 的解析 + 降级。
"""

from __future__ import annotations

import uuid

import pytest

from app.application.services.reactive_router import PlannerDecision, ReactiveRouter
from app.application.services.session_state import PlanView, SessionState, StepView
from app.domain.entities.agent import Agent
from app.domain.enums import AgentSystem


def _agent(name: str, tags: list[str]) -> Agent:
    return Agent(
        name=name, role="dev", avatar="",
        agent_system=AgentSystem.CLAUDE_CODE,
        capability_tags=tags, system_prompt="",
    )


_BE = _agent("后端阿强", ["backend", "api"])
_FE = _agent("前端小美", ["frontend", "ui"])
_QA = _agent("测试小测", ["testing"])


def _state(active_plan: PlanView | None = None) -> SessionState:
    # v4 事件驱动重构后 SessionState 删了 dispatch_mode 字段（commit 0b83e6a 起 "无 mode 枚举"），
    # 态由 active_plan 派生：None=纯对话，非 None=任务执行态。本地 dead kwarg 顺手清。
    return SessionState(
        session_id=uuid.uuid4(),
        members=(_BE, _FE, _QA),
        transcript=(),
        active_plan=active_plan,
    )


def _router(payload: dict | None = None, *, raises: bool = False) -> ReactiveRouter:
    async def fake(_state):
        if raises:
            raise RuntimeError("boom")
        return payload or {}
    return ReactiveRouter(raw_decide=fake)


# ── DTO 构造 ──


def test_planner_decision_defaults() -> None:
    d = PlannerDecision(action="relay", who=("后端阿强",))
    assert d.action == "relay"
    assert d.who == ("后端阿强",)
    assert d.requirement is None
    assert PlannerDecision.done("x").action == "done"


# ── decide 解析 + 降级 ──


@pytest.mark.asyncio
async def test_task_action() -> None:
    """action=task → 原样返回（不出 who）。"""
    d = await _router({"action": "task"}).decide(_state())
    assert d.action == "task"


@pytest.mark.asyncio
async def test_relay_resolves_who() -> None:
    """relay + 合法 who → 命中成员。"""
    d = await _router({"action": "relay", "who": ["后端阿强"]}).decide(_state())
    assert d.action == "relay"
    assert d.who == ("后端阿强",)


@pytest.mark.asyncio
async def test_relay_resolves_multiple() -> None:
    """relay 多名 → who 含全部命中成员（过滤无效）。"""
    d = await _router({"action": "relay", "who": ["后端阿强", "前端小美", "幽灵"]}).decide(_state())
    assert d.action == "relay"
    assert set(d.who) == {"后端阿强", "前端小美"}


@pytest.mark.asyncio
async def test_relay_unknown_who_degrades_to_done() -> None:
    """relay 选了不存在的成员 → who 过滤空 → 降级 done。"""
    d = await _router({"action": "relay", "who": ["查无此人"]}).decide(_state())
    assert d.action == "done"


@pytest.mark.asyncio
async def test_relay_who_as_string_tolerated() -> None:
    """容错：LLM 把 who 吐成字符串而非数组 → 仍命中。"""
    d = await _router({"action": "relay", "who": "后端阿强"}).decide(_state())
    assert d.action == "relay"
    assert d.who == ("后端阿强",)


@pytest.mark.asyncio
async def test_replan_parsed() -> None:
    """replan + requirement → 原样返回。"""
    plan = PlanView(steps=(StepView("B", "前端小美", "running"),))
    d = await _router(
        {"action": "replan", "requirement": "改成微服务架构"}
    ).decide(_state(plan))
    assert d.action == "replan"
    assert d.requirement == "改成微服务架构"


@pytest.mark.asyncio
async def test_replan_no_requirement_degrades_to_done() -> None:
    """replan 无 requirement 且无 reason → 降级 done。"""
    d = await _router({"action": "replan"}).decide(_state())
    assert d.action == "done"


@pytest.mark.asyncio
async def test_replan_falls_back_to_reason() -> None:
    """replan 无 requirement 但有 reason → 用 reason 当 requirement。"""
    d = await _router({"action": "replan", "reason": "改文档站"}).decide(_state())
    assert d.action == "replan"
    assert d.requirement == "改文档站"


@pytest.mark.asyncio
async def test_llm_error_degrades_to_done() -> None:
    """LLM 异常 → 降级 done，不抛。"""
    d = await _router(raises=True).decide(_state())
    assert d.action == "done"


@pytest.mark.asyncio
async def test_invalid_action_degrades() -> None:
    """非法 action → 降级 done。"""
    d = await _router({"action": "garbage"}).decide(_state())
    assert d.action == "done"


# ── dispatch_mode 进 prompt（v3 时代行为已废：v4 R2 删了 mode 枚举，AT_ROUTING / DISCUSSION
#    文本不再出现在 system prompt，原两条测试删除） ──


def test_transcript_labels_sender_by_name() -> None:
    """群聊记录每条标真名（不是匿名 Agent），系统消息标「系统」——decide 才能按「谁说的」路由。"""
    from app.domain.entities.message import Message
    from app.domain.enums import MessageRole

    # v4 R2 把 SYSTEM 消息从 history 过滤掉（噪音），但 transcript[0]（target）保留；
    # 把系统消息置首以验证 _fmt 对 SYSTEM role 的标签仍可达。原顺序 (agent, sys, user) 时
    # "系统: ✅" 落在 filtered history 里、assert 必挂。
    sys_msg = Message(session_id=uuid.uuid4(), role=MessageRole.SYSTEM, content="✅ t1 已完成")
    user_msg = Message(session_id=uuid.uuid4(), role=MessageRole.USER, content="你怎么看")
    agent_msg = Message(
        session_id=uuid.uuid4(), role=MessageRole.ASSISTANT,
        content="用 PG 还是 MySQL?", sender_agent_id=_BE.id,
    )
    state = SessionState(
        session_id=uuid.uuid4(), members=(_BE, _FE, _QA),
        transcript=(sys_msg, user_msg, agent_msg),
    )
    router = ReactiveRouter(raw_decide=lambda s: {})
    _, prompt = router._build_prompts(state)
    assert "系统: ✅" in prompt           # target 位置保留 _fmt("系统", SYSTEM) 标签
    assert "用户: 你怎么看" in prompt     # last_user 块保留
    assert "后端阿强: 用 PG" in prompt    # 真名，不是 "Agent"
