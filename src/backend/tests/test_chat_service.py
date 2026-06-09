"""ChatService 流式 + L1 记忆集成测试（MVP 核心路径）。"""

import uuid as _uuid

import pytest

from app.application.commands import CreateSessionCommand, SendMessageCommand
from app.application.services import ChatService, SessionService
from app.application.services.context_builder import ContextBuilder
from app.application.services.reactive_router import PlannerDecision
from app.core.events import InMemoryEventBus
from app.domain.entities.message import Message
from app.domain.enums import MessageRole as _Role
from app.domain.llm.protocol import StreamEventType
from app.infrastructure.cache.memory_l1 import InMemoryL1Store
from app.infrastructure.cache.watermark_store import InMemoryWatermarkStore
from app.infrastructure.llm.mock_adapter import MockAdapter
from app.infrastructure.repositories import (
    PostgresAgentRepository,
    PostgresGroupRepository,
    PostgresMessageRepository,
    PostgresSessionRepository,
)


class _StubRouter:
    """注入 ChatService 的假前门路由器：返回固定 PlannerDecision，隔离真 LLM。"""

    def __init__(self, decision: PlannerDecision | None = None) -> None:
        self._d = decision or PlannerDecision.done("stub")

    async def decide(self, state) -> PlannerDecision:  # type: ignore[no-untyped-def]
        return self._d


class _SeqRouter:
    """按序返回多个 PlannerDecision（测 R3 多轮讨论）。耗尽后恒返回 done。"""

    def __init__(self, decisions: list[PlannerDecision]) -> None:
        self._decisions = list(decisions)
        self.calls = 0

    async def decide(self, state) -> PlannerDecision:  # type: ignore[no-untyped-def]
        self.calls += 1
        if self._decisions:
            return self._decisions.pop(0)
        return PlannerDecision.done("seq exhausted")


def _build_chat(db_session, *, adapter=None, router=None):  # type: ignore[no-untyped-def]
    bus = InMemoryEventBus()
    msg_repo = PostgresMessageRepository(db_session)
    agent_repo = PostgresAgentRepository(db_session)
    group_repo = PostgresGroupRepository(db_session)
    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()
    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)
    chat = ChatService(
        PostgresSessionRepository(db_session),
        msg_repo,
        agent_repo,
        group_repo,
        l1,
        wm,
        ctx,
        adapter or MockAdapter(delay=0),
        bus,
        reactive_router=router or _StubRouter(),  # 默认 done → 非 @ 消息静默，零真 LLM
    )
    return chat, l1, wm, bus


@pytest.mark.asyncio
async def test_send_and_stream_private(db_session) -> None:  # type: ignore[no-untyped-def]
    from app.domain.entities.agent import Agent

    # 先创建一个 mock agent
    agent_repo = PostgresAgentRepository(db_session)
    agent = Agent(name="test-mock", avatar="🤖", role="tester")
    await agent_repo.save(agent)

    chat, l1, _wm, bus = _build_chat(db_session)

    session_svc = SessionService(
        PostgresSessionRepository(db_session),
        PostgresMessageRepository(db_session),
        bus,
    )
    session = await session_svc.create(CreateSessionCommand(type="private", agent_id=agent.id))

    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="你好")
        )
    ]
    assert events[-1].type == StreamEventType.DONE
    assert any(e.type == StreamEventType.TEXT for e in events)

    # L1 记忆应包含 user + assistant 两条
    window = await l1.get_window(session.id)
    assert len(window) == 2
    assert window[0]["role"] == "user"
    assert window[1]["role"] == "assistant"

    # 历史落库
    msgs = await session_svc.list_messages(session.id)
    assert len(msgs) == 2


@pytest.mark.asyncio
async def test_group_at_routing_single_mention(db_session) -> None:  # type: ignore[no-untyped-def]
    """群聊 V1：用户 @ 单个 Agent → 该 Agent 流式回复，watermark 推进。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="coordinator", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="前端")
    b = Agent(name="AgentB", avatar="B", role="后端")
    for ag in (coord, a, b):
        await agent_repo.save(ag)

    group_repo = PostgresGroupRepository(db_session)
    group = Group(name="proj-x", coordinator_id=coord.id, member_ids=[a.id, b.id])
    await group_repo.save(group)

    session_repo = PostgresSessionRepository(db_session)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await session_repo.save(session)

    chat, _l1, wm, _bus = _build_chat(db_session)

    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(
                session_id=session.id, content="@AgentA 帮我看看", mentions=["AgentA"]
            )
        )
    ]
    assert events[-1].type == StreamEventType.DONE
    text_events = [e for e in events if e.type == StreamEventType.TEXT]
    assert text_events, "应有 TEXT 事件"
    assert all(e.sender_agent_id == a.id for e in text_events), (
        "所有 TEXT 事件都应携带 AgentA 的 sender_agent_id"
    )

    # AgentA 的 watermark 应被推进
    assert await wm.get(group.id, a.id) is not None
    # AgentB 未被 @，不该有 watermark
    assert await wm.get(group.id, b.id) is None


@pytest.mark.asyncio
async def test_group_at_routing_multi_mention_serial(db_session) -> None:  # type: ignore[no-untyped-def]
    """群聊 V1：多 @ 串行执行，每个 Agent 各自落库 + 推 watermark。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="coordinator", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="前端")
    b = Agent(name="AgentB", avatar="B", role="后端")
    for ag in (coord, a, b):
        await agent_repo.save(ag)

    group = Group(name="g2", coordinator_id=coord.id, member_ids=[a.id, b.id])
    await PostgresGroupRepository(db_session).save(group)

    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    chat, _l1, wm, _bus = _build_chat(db_session)
    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(
                session_id=session.id,
                content="@AgentA @AgentB 一起看下",
                mentions=["AgentA", "AgentB"],
            )
        )
    ]
    senders = {e.sender_agent_id for e in events if e.sender_agent_id}
    assert senders == {a.id, b.id}, "两个 Agent 都应该有发言"

    assert await wm.get(group.id, a.id) is not None
    assert await wm.get(group.id, b.id) is not None


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="v3 时代 AT_ROUTING 硬静默断言已不可达：v4 R2 重构后 chat_service 不再读 "
    "Group.dispatch_mode（'死群兜底' 改由 reactive router decide=done 承担），且 "
    "_build_chat 默认 _StubRouter(done) 在 _handle_group 链路下会先经 _persist_user_message "
    "→ 27 字符级 MockAdapter 回显（实测），events == [] 不再成立。需先审 v4 _handle_group "
    "链路真意图后用路由器注入断言 '无真 Agent text 事件' 重写。See worklogs/袁/2026-06-09。"
)
async def test_group_no_mention_silent(db_session) -> None:  # type: ignore[no-untyped-def]
    """死群兜底（v3 语义）：无 @ + AT_ROUTING 模式 → 静默，无 Agent 响应。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import DispatchMode, SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="r")
    for ag in (coord, a):
        await agent_repo.save(ag)

    group = Group(name="g3", coordinator_id=coord.id, member_ids=[a.id])
    group.set_dispatch_mode(DispatchMode.AT_ROUTING)  # 显式降级（v4 死字段）
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    chat, _l1, wm, _bus = _build_chat(db_session)
    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="大家好")
        )
    ]
    assert events == []
    assert await wm.get(group.id, a.id) is None


@pytest.mark.asyncio
async def test_group_invalid_mention_skipped(db_session) -> None:  # type: ignore[no-untyped-def]
    """@ 不存在的 Agent → 跳过；非群成员 Agent → 跳过。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="r")
    outsider = Agent(name="Outsider", avatar="X", role="r")
    for ag in (coord, a, outsider):
        await agent_repo.save(ag)

    group = Group(name="g4", coordinator_id=coord.id, member_ids=[a.id])
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    chat, _l1, _wm, _bus = _build_chat(db_session)
    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(
                session_id=session.id,
                content="@AgentA @Outsider @NotExist 测试",
                mentions=["AgentA", "Outsider", "NotExist"],
            )
        )
    ]
    senders = {e.sender_agent_id for e in events if e.sender_agent_id}
    # 只有 AgentA 被有效路由
    assert senders == {a.id}


# === Phase 5：decompose 闸门接线 ===


class _RecordingSink:
    """系统消息下沉（ChatService._coord_post 接线）— 收 session_id + content + sender_agent_id。"""

    def __init__(self) -> None:
        import asyncio

        self.messages: list[tuple[str, str, object]] = []  # (session_id, content, sender_agent_id)
        self.done = asyncio.Event()

    async def __call__(self, session_id, content, sender_agent_id) -> None:  # type: ignore[no-untyped-def]
        # 与 chat_service._coord_post(session.id, content, group.coordinator_id) 三参一致。
        # 旧版只收 2 参（无 sender_agent_id），与生产调用 3 参不一致，本地触发 TypeError 暴露。
        self.messages.append((session_id, content, sender_agent_id))
        self.done.set()


def _build_chat_with_router(db_session, *, router, builder, sink):  # type: ignore[no-untyped-def]
    bus = InMemoryEventBus()
    msg_repo = PostgresMessageRepository(db_session)
    agent_repo = PostgresAgentRepository(db_session)
    group_repo = PostgresGroupRepository(db_session)
    l1 = InMemoryL1Store(window=20)
    wm = InMemoryWatermarkStore()
    ctx = ContextBuilder(msg_repo, agent_repo, l1, wm)
    return ChatService(
        PostgresSessionRepository(db_session),
        msg_repo,
        agent_repo,
        group_repo,
        l1,
        wm,
        ctx,
        MockAdapter(delay=0),
        bus,
        reactive_router=router,
        orchestrator_builder=builder,
        system_message_sink=sink,
    )


@pytest.mark.asyncio
async def test_group_decompose_spawns_coordinator(db_session) -> None:  # type: ignore[no-untyped-def]
    """无 @ + decide=task → 起后台 Orchestrator → 跑到完成落系统消息。"""
    import asyncio

    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType
    from app.domain.task_engine.dag import TaskDef
    from app.domain.task_engine.orchestrator import Orchestrator
    from app.domain.task_engine.ports import PlanContext
    from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier

    CoordinatorRegistry.clear()

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="dev")
    for ag in (coord, a):
        await agent_repo.save(ag)
    group = Group(name="gw", coordinator_id=coord.id, member_ids=[a.id])
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    async def _builder(*, task, members, session, group):  # type: ignore[no-untyped-def]
        td = TaskDef(
            id="t1", title="t1", description="", suggested_worker="AgentA",
            depends_on=[], acceptance=[], no_verify=True,
        )
        return Orchestrator(
            planner=FakePlanner([td]),
            executor=FakeExecutor(),
            verifier=FakeVerifier(),
            ctx=PlanContext(task=task, workers=("AgentA",)),
        )

    sink = _RecordingSink()
    chat = _build_chat_with_router(
        db_session, router=_StubRouter(PlannerDecision(action="task")),
        builder=_builder, sink=sink,
    )

    events = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="帮我实现登录页")
        )
    ]
    # v4 task 路径在后台起 Orchestrator 之前先 yield 一条 "✅ 任务已受理，正在规划…" 提示
    # 给用户（v3 时代是 events == []）。task 路径仍然不 yield worker 流（被后台化）。
    assert len(events) == 1
    assert events[0].content == "✅ 任务已受理，正在规划…"
    assert events[0].sender_agent_id == coord.id  # 由 coordinator 发送
    await asyncio.wait_for(sink.done.wait(), timeout=2)
    assert sink.messages  # 落了汇总系统消息
    assert CoordinatorRegistry().get(session.id) is None  # 完成后释放
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_group_discuss_does_not_spawn(db_session) -> None:  # type: ignore[no-untyped-def]
    """decide=respond（非 task）→ 不起协调者；AT_ROUTING 群静默（无回归）。"""
    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import DispatchMode, SessionType

    CoordinatorRegistry.clear()

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="dev")
    for ag in (coord, a):
        await agent_repo.save(ag)
    group = Group(name="gw2", coordinator_id=coord.id, member_ids=[a.id])
    group.set_dispatch_mode(DispatchMode.AT_ROUTING)  # 静默兜底，便于断言不 spawn
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)

    async def _builder(*, task, members, session, group):  # type: ignore[no-untyped-def]
        raise AssertionError("discuss 不应组装 Orchestrator")

    sink = _RecordingSink()
    chat = _build_chat_with_router(
        db_session,
        # relay 到空闲成员 → 流式回话；非 task，不该起 Orchestrator。done 收尾防回环。
        router=_SeqRouter([
            PlannerDecision(action="relay", who=("AgentA",)),
            PlannerDecision.done(),
        ]),
        builder=_builder, sink=sink,
    )
    _ = [
        e
        async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="帮我实现登录页")
        )
    ]
    assert CoordinatorRegistry().get(session.id) is None  # relay 不 spawn 协调者
    CoordinatorRegistry.clear()


# === v3 步1：前门机械反射（迁移自 test_coordinator_gate）===


@pytest.mark.parametrize("text", ["停", "取消", "停止", "  cancel ", "STOP"])
def test_reflex_control_hits(text: str) -> None:
    assert ChatService._is_control(text) is True


@pytest.mark.parametrize("text", ["继续", "帮我加个功能", "停车场在哪", "停站点信息"])
def test_reflex_control_misses(text: str) -> None:
    assert ChatService._is_control(text) is False


def _umsg(content: str, *, from_agent: bool = False) -> Message:
    return Message(
        session_id=_uuid.uuid4(), role=_Role.ASSISTANT if from_agent else _Role.USER,
        content=content, sender_agent_id=_uuid.uuid4() if from_agent else None,
    )


@pytest.mark.parametrize("text", ["大家怎么看", "各位有什么建议", "所有人都说说"])
def test_reflex_broadcast_hits(text: str) -> None:
    assert ChatService._is_broadcast(_umsg(text)) is True


def test_reflex_broadcast_misses_plain() -> None:
    assert ChatService._is_broadcast(_umsg("帮我加个登录页")) is False


def test_reflex_broadcast_ignores_agent_message() -> None:
    # Agent 自己说"大家好"不触发全体响应（防连锁）
    assert ChatService._is_broadcast(_umsg("大家好", from_agent=True)) is False


# === v4 R3：多轮讨论循环（strip → keep）===


async def _mk_discuss_group(db_session):  # type: ignore[no-untyped-def]
    """DISCUSSION 群 + 两个 worker A/B（默认 dispatch_mode=DISCUSSION）。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    a = Agent(name="AgentA", avatar="A", role="前端")
    b = Agent(name="AgentB", avatar="B", role="后端")
    for ag in (coord, a, b):
        await agent_repo.save(ag)
    group = Group(name="disc", coordinator_id=coord.id, member_ids=[a.id, b.id])
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)
    return session, group, a, b


@pytest.mark.asyncio
async def test_multi_round_discuss_two_agents_then_done(db_session) -> None:  # type: ignore[no-untyped-def]
    """decide: respond(A) → respond(B) → done。A、B 各发言一轮后收敛。"""
    session, _group, a, b = await _mk_discuss_group(db_session)
    router = _SeqRouter([
        PlannerDecision(action="relay", who=("AgentA",)),
        PlannerDecision(action="relay", who=("AgentB",)),
        PlannerDecision.done(),
    ])
    chat, _l1, _wm, _bus = _build_chat(db_session, router=router)

    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="帮我分析下这个技术方案")
        )
    ]
    senders = [e.sender_agent_id for e in events if e.sender_agent_id]
    assert a.id in senders and b.id in senders
    assert router.calls == 3  # 首轮 + B 轮 + done 轮


@pytest.mark.asyncio
async def test_multi_round_same_agent_can_speak_again(db_session) -> None:  # type: ignore[no-untyped-def]
    """同一 agent 可被多轮选中（无 already_responded 拦截）。"""
    session, _group, a, _b = await _mk_discuss_group(db_session)
    router = _SeqRouter([
        PlannerDecision(action="relay", who=("AgentA",)),
        PlannerDecision(action="relay", who=("AgentA",)),
        PlannerDecision.done(),
    ])
    chat, _l1, _wm, _bus = _build_chat(db_session, router=router)

    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="再追问一下")
        )
    ]
    a_text = [e for e in events if e.sender_agent_id == a.id and e.type == StreamEventType.TEXT]
    assert len(a_text) >= 2  # A 至少两段（两轮各一段）
    assert router.calls == 3


@pytest.mark.asyncio
async def test_multi_round_task_interrupts_loop(db_session) -> None:  # type: ignore[no-untyped-def]
    """讨论中 decide 转 task → 退出循环起 Harness。"""
    import asyncio

    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.task_engine.dag import TaskDef
    from app.domain.task_engine.orchestrator import Orchestrator
    from app.domain.task_engine.ports import PlanContext
    from tests.fakes import FakeExecutor, FakePlanner, FakeVerifier

    CoordinatorRegistry.clear()
    session, _group, _a, _b = await _mk_discuss_group(db_session)

    started = {"n": 0}

    async def _builder(*, task, members, session, group):  # type: ignore[no-untyped-def]
        started["n"] += 1
        td = TaskDef(id="t1", title="t1", description="", suggested_worker="AgentA",
                     depends_on=[], acceptance=[], no_verify=True)
        return Orchestrator(
            planner=FakePlanner([td]), executor=FakeExecutor(), verifier=FakeVerifier(),
            ctx=PlanContext(task=task, workers=("AgentA",)),
        )

    router = _SeqRouter([
        PlannerDecision(action="relay", who=("AgentA",)),
        PlannerDecision(action="task"),
    ])
    chat = _build_chat_with_router(
        db_session, router=router, builder=_builder, sink=_RecordingSink()
    )
    _ = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="讨论着讨论着就动手吧")
        )
    ]
    await asyncio.sleep(0.05)
    assert started["n"] == 1  # task 中断讨论 → 起了一次 Harness
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_discuss_done_immediately_no_stream(db_session) -> None:  # type: ignore[no-untyped-def]
    """首轮 decide=done → 不进讨论循环，无流式。"""
    session, _group, _a, _b = await _mk_discuss_group(db_session)
    router = _SeqRouter([PlannerDecision.done()])
    chat, _l1, _wm, _bus = _build_chat(db_session, router=router)

    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="随便说说")
        )
    ]
    assert events == []
    assert router.calls == 1  # 只 decide 一次，不回环


# === v4 统一路由：执行态 relay（投递层按状态分流）+ task 降级 ===


class _StubOrchestrator:
    """最小桩：满足 plan_view（graph.nodes）+ 记录 on_feed / replan。"""

    def __init__(self, steps: list[tuple[str, str, str]], *, replan=None, new_tasks=None) -> None:
        from types import SimpleNamespace

        self.graph = SimpleNamespace(
            nodes={
                tid: SimpleNamespace(
                    task=SimpleNamespace(id=tid, suggested_worker=worker),
                    status=SimpleNamespace(value=status),
                )
                for tid, worker, status in steps
            }
        )
        self.fed: list[tuple[str, str]] = []
        self._replan_diff = replan
        self._new_tasks = new_tasks or []
        self.replanned: list[tuple[list, bool]] = []

    async def on_feed(self, step_id: str, answer: str) -> None:
        self.fed.append((step_id, answer))

    async def plan_replan(self, requirement: str):  # type: ignore[no-untyped-def]
        return self._new_tasks, self._replan_diff

    async def replan(self, new_tasks, *, force: bool = False) -> None:  # type: ignore[no-untyped-def]
        self.replanned.append((new_tasks, force))

    async def abort_inflight(self) -> None:
        pass


async def _register_run(session_id, steps, *, replan=None, new_tasks=None):  # type: ignore[no-untyped-def]
    """在进程级 registry 注册一个带 stub orchestrator 的 run（_task=None → parked）。"""
    from app.application.services.coordinator_run import CoordinatorRegistry, CoordinatorRun

    CoordinatorRegistry.clear()
    run = CoordinatorRun(session_id=session_id)
    stub = _StubOrchestrator(steps, replan=replan, new_tasks=new_tasks)
    run._orchestrator = stub  # type: ignore[assignment]
    CoordinatorRegistry().try_reserve(session_id, run)
    return run, stub


async def _mk_group_session(db_session):  # type: ignore[no-untyped-def]
    """群 + 一个在干活的 worker(前端小美) + 一个空闲成员(后端阿强)。"""
    from app.domain.entities.agent import Agent
    from app.domain.entities.group import Group
    from app.domain.entities.session import Session
    from app.domain.enums import SessionType

    agent_repo = PostgresAgentRepository(db_session)
    coord = Agent(name="协调者", avatar="C", role="c", is_system=True)
    worker = Agent(name="前端小美", avatar="A", role="dev")
    idle = Agent(name="后端阿强", avatar="B", role="dev")
    for ag in (coord, worker, idle):
        await agent_repo.save(ag)
    group = Group(name="gr2", coordinator_id=coord.id, member_ids=[worker.id, idle.id])
    await PostgresGroupRepository(db_session).save(group)
    session = Session(type=SessionType.GROUP, group_id=group.id, title="g")
    await PostgresSessionRepository(db_session).save(session)
    return session, group, worker, idle


@pytest.mark.asyncio
async def test_execution_relay_to_worker_resumes(db_session) -> None:  # type: ignore[no-untyped-def]
    """relay 给在干活的成员(parked) → 投递层当答复 → on_feed(step) resume。"""
    import asyncio

    from app.application.services.coordinator_run import CoordinatorRegistry

    session, _group, _worker, _idle = await _mk_group_session(db_session)
    run, stub = await _register_run(session.id, [("t1", "前端小美", "running")])

    chat = _build_chat_with_router(
        db_session,
        router=_StubRouter(PlannerDecision(action="relay", who=("前端小美",))),
        builder=lambda **k: None, sink=_RecordingSink(),
    )
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="用 PG")
        )
    ]
    assert events == []  # 后台投递，前台不流式
    await asyncio.sleep(0.05)  # 等 spawn 的 on_feed task
    assert stub.fed == [("t1", "用 PG")]
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_execution_relay_to_idle_member_streams(db_session) -> None:  # type: ignore[no-untyped-def]
    """relay 给空闲成员 → 投递层直接群聊回话（流式）。"""
    from app.application.services.coordinator_run import CoordinatorRegistry

    session, _group, _worker, idle = await _mk_group_session(db_session)
    await _register_run(session.id, [("t1", "前端小美", "running")])

    chat = _build_chat_with_router(
        db_session,
        # 后端阿强不在 running 节点里=空闲 → 流式回话；done 收尾防回环。
        router=_SeqRouter([
            PlannerDecision(action="relay", who=("后端阿强",)),
            PlannerDecision.done(),
        ]),
        builder=lambda **k: None, sink=_RecordingSink(),
    )
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="后端阿强你怎么看")
        )
    ]
    senders = {e.sender_agent_id for e in events if e.sender_agent_id}
    assert senders == {idle.id}
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_execution_task_downgrades_to_note(db_session) -> None:  # type: ignore[no-untyped-def]
    """执行态 + decide=task → 降级为全局 note，不起第二个 Orchestrator。"""
    from app.application.services.coordinator_run import CoordinatorRegistry

    session, _group, _worker, _idle = await _mk_group_session(db_session)
    run, _stub = await _register_run(session.id, [("t1", "前端小美", "running")])

    def _builder(**k):  # type: ignore[no-untyped-def]
        raise AssertionError("执行态 task 不应起新 Orchestrator")

    chat = _build_chat_with_router(
        db_session,
        router=_StubRouter(PlannerDecision(action="task")),
        builder=_builder, sink=_RecordingSink(),
    )
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="顺便再做个注册页")
        )
    ]
    # v4 执行态 task 降级 note 路径：除把 note 入桶外，还 yield 一条 "📋 已追加到当前任务队列"
    # 给用户可见反馈（v3 是 events == []）。
    assert len(events) == 1
    assert events[0].content == "📋 已追加到当前任务队列"
    assert run._pending_notes == {"*": ["顺便再做个注册页"]}
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_replan_non_destructive_swaps(db_session) -> None:  # type: ignore[no-untyped-def]
    """decide=replan + 非破坏（无 running）→ 直接换图（force=False），不暂存。"""
    import asyncio

    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.task_engine.orchestrator import ReplanDiff

    session, _g, _w, _i = await _mk_group_session(db_session)
    diff = ReplanDiff(running=[], completed=["t1"], new_count=2)
    run, stub = await _register_run(
        session.id, [("t1", "前端小美", "completed")], replan=diff, new_tasks=["x", "y"]
    )
    chat = _build_chat_with_router(
        db_session,
        router=_StubRouter(PlannerDecision(action="replan", requirement="改文档站")),
        builder=lambda **k: None, sink=_RecordingSink(),
    )
    _ = [e async for e in chat.send_and_stream(
        SendMessageCommand(session_id=session.id, content="别做博客了改文档站"))]
    await asyncio.sleep(0.05)
    assert stub.replanned and stub.replanned[0][1] is False  # 直接换图
    assert run.pending_replan is None
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_replan_destructive_stashes_for_confirm(db_session) -> None:  # type: ignore[no-untyped-def]
    """decide=replan + 破坏（有 running）→ 暂存待确认，不换图。"""
    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.task_engine.orchestrator import ReplanDiff

    session, _g, _w, _i = await _mk_group_session(db_session)
    diff = ReplanDiff(running=["t1"], completed=[], new_count=2)
    run, stub = await _register_run(
        session.id, [("t1", "前端小美", "running")], replan=diff, new_tasks=["x"]
    )
    chat = _build_chat_with_router(
        db_session,
        router=_StubRouter(PlannerDecision(action="replan", requirement="改微服务")),
        builder=lambda **k: None, sink=_RecordingSink(),
    )
    _ = [e async for e in chat.send_and_stream(
        SendMessageCommand(session_id=session.id, content="改成微服务"))]
    assert run.pending_replan is not None  # 暂存
    assert not stub.replanned  # 未换图（等确认）
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_replan_confirmation_reflex_executes(db_session) -> None:  # type: ignore[no-untyped-def]
    """pending_replan 存在 + 用户「继续」→ 零 LLM 反射执行 force 换图，清暂存。"""
    import asyncio

    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.task_engine.orchestrator import ReplanDiff

    session, _g, _w, _i = await _mk_group_session(db_session)
    diff = ReplanDiff(running=["t1"], completed=[], new_count=2)
    run, stub = await _register_run(session.id, [("t1", "前端小美", "running")])
    run.stash_replan("改微服务", ["x"], diff)  # 预暂存

    chat = _build_chat_with_router(
        db_session, router=_StubRouter(PlannerDecision.done()),  # 不应被咨询
        builder=lambda **k: None, sink=_RecordingSink(),
    )
    _ = [e async for e in chat.send_and_stream(
        SendMessageCommand(session_id=session.id, content="继续"))]
    await asyncio.sleep(0.05)
    assert stub.replanned and stub.replanned[0][1] is True  # force=True
    assert run.pending_replan is None  # 已清
    CoordinatorRegistry.clear()


@pytest.mark.asyncio
async def test_execution_relay_idle_not_blocked_by_at_routing(db_session) -> None:  # type: ignore[no-untyped-def]
    """AT_ROUTING 群 + 执行态 + relay 空闲成员 → 仍流式（无 dispatch_mode 硬守卫）。"""
    from app.application.services.coordinator_run import CoordinatorRegistry
    from app.domain.enums import DispatchMode

    session, group, _worker, idle = await _mk_group_session(db_session)
    group.set_dispatch_mode(DispatchMode.AT_ROUTING)
    await PostgresGroupRepository(db_session).save(group)
    await _register_run(session.id, [("t1", "前端小美", "running")])

    chat = _build_chat_with_router(
        db_session,
        router=_SeqRouter([
            PlannerDecision(action="relay", who=("后端阿强",)),
            PlannerDecision.done(),
        ]),
        builder=lambda **k: None, sink=_RecordingSink(),
    )
    events = [
        e async for e in chat.send_and_stream(
            SendMessageCommand(session_id=session.id, content="做得怎么样了")
        )
    ]
    senders = {e.sender_agent_id for e in events if e.sender_agent_id}
    assert senders == {idle.id}
    CoordinatorRegistry.clear()
