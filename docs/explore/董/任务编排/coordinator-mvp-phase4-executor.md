# Phase 4 详细实现方案 — Executor（派真群成员 Agent）

> 日期：2026-06-06 | 属于：[[coordinator-mvp-implementation-plan]] Phase 4 | 依据：[[coordinator-mvp-phase4-executor-spec]]
> 前提：M1 + Phase 2（Verifier）+ Phase 3（Planner）已落地（91 测试绿）。
> 决策已定：**D1 新写 `build_task_request`**（不复用 build_for_agent 的群聊回复语义）；**D2 输出走任务面板**（event_sink，不刷屏聊天）。

---

## 0. 本相目标

换掉 `FakeExecutor`，派真群成员 Agent 执行任务。MVP：串行、无 worktree、硬超时；复用 `build_adapter_for_agent + adapter.stream`。

核心逻辑（解析 worker → 构造任务请求 → 收流 → 判 ok/error/超时）用 **fake adapter** 全测，**不起真 CLI**。

---

## 1. 已核对的字段（照着写，非猜测）

```python
# protocol.py 实测
AgentRequest(request_id: str, session_id: UUID, messages: list[dict],
             system_prompt: str|None, available_tools: list[str],
             working_directory: str|None, agent_id: UUID|None,
             group_id: UUID|None, is_group_chat: bool, has_history: bool, ...)
StreamEvent(type: StreamEventType, seq, content, tool_call, tool_result, metadata, sender_agent_id)
StreamEventType: TEXT THINKING TOOL_CALL TOOL_RESULT REQUEST_APPROVAL TASK_PLAN ERROR DONE
# factory.py
build_adapter_for_agent(agent: Agent) -> UnifiedAgent   # 有 .stream(request) -> AsyncIterator[StreamEvent]
# Agent 实体：name/role/provider/model/system_prompt/skills/capability_tags（无显式 tools 字段）
```

---

## 2. 新建 `executor.py`

```python
"""Executor — 派群成员 Agent 执行任务（spec §1）。

代码（非 LLM）：解析 worker → 构造任务请求（D1）→ adapter.stream → 收流 → WorkerOutcome。
永不抛异常给 Orchestrator——所有失败收敛成 WorkerOutcome(ok=False)（spec §3）。
worker 流事件 → event_sink（D2，任务面板；MVP 默认 no-op）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from app.domain.entities.agent import Agent
from app.domain.llm.protocol import AgentRequest, StreamEvent, StreamEventType
from app.domain.task_engine.dag import TaskNode
from app.domain.task_engine.ports import WorkerOutcome

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600.0  # 单任务墙钟上限（秒）

# 任务执行契约（D1：不是群聊回复，是"干这个活"）
TASK_EXEC_CONTRACT = (
    "你被分配了一个具体任务。请直接完成它（写代码/改文件/跑命令），不要闲聊或只回复。"
    "严格遵守下方约束与验收标准。完成后用一句话说明你做了什么。"
)

ResolveAgent = Callable[[str], Agent | None]
AdapterFactory = Callable[[Agent], object]  # 返回有 .stream(request) 的 UnifiedAgent
EventSink = Callable[[StreamEvent], Awaitable[None]]


def build_task_instruction(node: TaskNode) -> str:
    """TaskDef → 任务指令文本（D1）。"""
    t = node.task
    parts = [f"# 任务：{t.title}", t.description or ""]
    mech = [c.spec for c in t.acceptance if c.kind == "mechanical"]
    if mech:
        parts.append("## 验收（你的产出必须让这些命令通过）\n"
                     + "\n".join(f"- `{s}`" for s in mech))
    return "\n\n".join(p for p in parts if p)


def build_task_request(
    node: TaskNode, agent: Agent, *, session_id: UUID, group_id: UUID, workspace: str | None
) -> AgentRequest:
    """构造任务执行请求（D1：指令做 content，任务契约做 sp，非群聊回复）。"""
    system_prompt = "\n\n".join(filter(None, [agent.system_prompt, TASK_EXEC_CONTRACT]))
    return AgentRequest(
        request_id=str(uuid4()),
        session_id=session_id,
        messages=[{"role": "user", "content": build_task_instruction(node)}],
        system_prompt=system_prompt,
        available_tools=[],  # CLI 运行时忽略此字段（CLI 二进制自带全工具）；仅 API adapter 用它
        working_directory=node.worktree or workspace,
        agent_id=agent.id,
        group_id=group_id,
        is_group_chat=True,
        has_history=False,  # MVP：每个任务一次性派发
    )


class AgentExecutor:
    """派群成员 Agent 执行单任务。串行无 worktree（spec §1.2）。"""

    def __init__(
        self,
        *,
        resolve_agent: ResolveAgent,
        adapter_factory: AdapterFactory,
        session_id: UUID,
        group_id: UUID,
        workspace: str | None,
        timeout: float = DEFAULT_TIMEOUT,
        event_sink: EventSink | None = None,  # D2：worker 流 → 任务面板
    ) -> None:
        self._resolve = resolve_agent
        self._adapter_factory = adapter_factory
        self._session_id = session_id
        self._group_id = group_id
        self._workspace = workspace
        self._timeout = timeout
        self._sink = event_sink

    async def run(self, node: TaskNode) -> WorkerOutcome:
        agent = self._resolve(node.task.suggested_worker)
        if agent is None:
            return WorkerOutcome(ok=False, output=f"worker 不存在: {node.task.suggested_worker}")

        request = build_task_request(
            node, agent, session_id=self._session_id,
            group_id=self._group_id, workspace=self._workspace,
        )
        adapter = self._adapter_factory(agent)

        try:
            output, errored, blocked = await asyncio.wait_for(
                self._consume(adapter, request), timeout=self._timeout
            )
        except TimeoutError:
            logger.warning("worker 执行超时 task=%s", node.task.id)
            return WorkerOutcome(ok=False, output=f"执行超时（>{self._timeout}s）")
        except Exception as exc:  # 流崩/CLI 错 → 收敛，不抛给 Orchestrator
            logger.exception("worker 执行失败 task=%s", node.task.id)
            return WorkerOutcome(ok=False, output=f"执行失败: {exc}")

        if errored:
            return WorkerOutcome(ok=False, output=f"worker 报错: {errored}")
        if blocked:
            return WorkerOutcome(ok=False, output="worker 需要审批（MVP 不支持）")
        return WorkerOutcome(ok=True, output=output)

    async def _consume(self, adapter, request) -> tuple[str, str | None, bool]:
        """消费事件流：收集 TEXT、捕获 ERROR、检测 REQUEST_APPROVAL。事件转发 sink（D2）。"""
        chunks: list[str] = []
        errored: str | None = None
        blocked = False
        async for evt in adapter.stream(request):
            if self._sink is not None:
                await self._sink(evt)  # D2：推任务面板/WS
            if evt.type == StreamEventType.TEXT and evt.content:
                chunks.append(evt.content)
            elif evt.type == StreamEventType.ERROR:
                errored = evt.content or "worker error"
            elif evt.type == StreamEventType.REQUEST_APPROVAL:
                blocked = True
        return "".join(chunks), errored, blocked
```

---

## 3. 新建 `tests/test_executor.py`（fake adapter，不起真 CLI）

```python
"""Executor 测试（spec §1.4）。fake adapter yield 预设 StreamEvent，确定性。"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.domain.entities.agent import Agent
from app.domain.enums import Provider
from app.domain.llm.protocol import StreamEvent, StreamEventType
from app.domain.task_engine.dag import Check, TaskDef, TaskNode
from app.domain.task_engine.executor import AgentExecutor


def _agent(name="前端Agent"):
    return Agent(name=name, avatar="x", role="dev", provider=Provider.ANTHROPIC, model="m")


def _node(worker="前端Agent"):
    task = TaskDef(id="t1", title="建页面", suggested_worker=worker,
                   acceptance=[Check("mechanical", "true")])
    return TaskNode(task=task)


def _evt(t, content=None, seq=0):
    return StreamEvent(type=t, seq=seq, content=content)


class FakeAdapter:
    """yield 预设事件序列；slow=True 时每个事件前 sleep（测超时）。"""
    def __init__(self, events, slow=0.0):
        self._events = events
        self._slow = slow

    async def stream(self, request):
        for e in self._events:
            if self._slow:
                await asyncio.sleep(self._slow)
            yield e


def _exec(adapter, resolve=None):
    return AgentExecutor(
        resolve_agent=resolve or (lambda name: _agent(name)),
        adapter_factory=lambda agent: adapter,
        session_id=uuid4(), group_id=uuid4(), workspace="/tmp", timeout=2.0,
    )


@pytest.mark.asyncio
async def test_normal_completion_ok():
    adapter = FakeAdapter([
        _evt(StreamEventType.THINKING, "想"),
        _evt(StreamEventType.TEXT, "创建了 LoginForm.tsx"),
        _evt(StreamEventType.DONE),
    ])
    result = await _exec(adapter).run(_node())
    assert result.ok
    assert "LoginForm" in result.output


@pytest.mark.asyncio
async def test_worker_not_found():
    result = await _exec(FakeAdapter([]), resolve=lambda name: None).run(_node())
    assert not result.ok
    assert "worker 不存在" in result.output


@pytest.mark.asyncio
async def test_stream_error_fails():
    adapter = FakeAdapter([_evt(StreamEventType.ERROR, "CLI 崩了")])
    result = await _exec(adapter).run(_node())
    assert not result.ok
    assert "报错" in result.output


@pytest.mark.asyncio
async def test_approval_blocks():
    adapter = FakeAdapter([_evt(StreamEventType.REQUEST_APPROVAL, "需批准 rm")])
    result = await _exec(adapter).run(_node())
    assert not result.ok
    assert "审批" in result.output


@pytest.mark.asyncio
async def test_timeout_fails():
    adapter = FakeAdapter([_evt(StreamEventType.TEXT, "慢")] * 10, slow=1.0)
    result = await _exec(adapter).run(_node())  # timeout=2.0
    assert not result.ok
    assert "超时" in result.output


@pytest.mark.asyncio
async def test_adapter_raises_caught():
    class BoomAdapter:
        async def stream(self, request):
            raise RuntimeError("boom")
            yield  # noqa
    result = await _exec(BoomAdapter()).run(_node())
    assert not result.ok
    assert "执行失败" in result.output


@pytest.mark.asyncio
async def test_event_sink_receives_events():
    seen = []

    async def sink(evt):
        seen.append(evt)

    adapter = FakeAdapter([_evt(StreamEventType.TEXT, "x"), _evt(StreamEventType.DONE)])
    ex = AgentExecutor(
        resolve_agent=lambda n: _agent(n), adapter_factory=lambda a: adapter,
        session_id=uuid4(), group_id=uuid4(), workspace="/tmp",
        event_sink=sink,
    )
    await ex.run(_node())
    assert len(seen) == 2
```

> 注：`test_event_sink` 用 async sink；上面示意，落地时直接写 `event_sink=_collect(seen)`。

---

## 4. e2e — Orchestrator + 真 Executor(fake adapter) + 真 Verifier

加到 `tests/test_orchestrator.py`（`_t`/`FakePlanner` 已在 Phase 1 定义于此文件作用域，无需额外 import）：

```python
@pytest.mark.asyncio
async def test_e2e_orchestrator_executor_verifier(tmp_path):
    """真 Orchestrator + 真 AgentExecutor(fake adapter) + 真 MechanicalVerifier → COMPLETED。"""
    from uuid import uuid4
    from app.domain.entities.agent import Agent
    from app.domain.enums import Provider
    from app.domain.llm.protocol import StreamEvent, StreamEventType
    from app.domain.task_engine.executor import AgentExecutor
    from app.domain.task_engine.verifier import MechanicalVerifier

    class FakeAdapter:
        async def stream(self, request):
            yield StreamEvent(type=StreamEventType.TEXT, seq=0, content="done")
            yield StreamEvent(type=StreamEventType.DONE, seq=1)

    planner = FakePlanner([_t("t1")])  # acceptance=[Check("mechanical","true")]
    executor = AgentExecutor(
        resolve_agent=lambda n: Agent(name=n, avatar="x", role="d",
                                      provider=Provider.ANTHROPIC, model="m"),
        adapter_factory=lambda a: FakeAdapter(),
        session_id=uuid4(), group_id=uuid4(), workspace=str(tmp_path),
    )
    verifier = MechanicalVerifier(workspace=str(tmp_path))  # 跑真命令 "true"
    orch = Orchestrator(planner=planner, executor=executor, verifier=verifier, ctx=_ctx())
    result = await orch.run()
    assert result.reason == ExitReason.COMPLETED
```

证明：Planner → Orchestrator 调度 → **真 Executor 派发(fake adapter)** → **真 Verifier 跑命令** → COMPLETED。整条 MVP 链路打通（仅 LLM/CLI 是 fake）。

---

## 5. 与 Orchestrator / Phase 5 的接法

```python
# Phase 5 构造（真）
from app.infrastructure.llm.factory import build_adapter_for_agent
executor = AgentExecutor(
    resolve_agent=lambda name: agent_repo.get_by_name_in_group(name, group_id),
    adapter_factory=build_adapter_for_agent,        # ← 复用现有工厂
    session_id=session.id, group_id=group.id,
    workspace=session.workspace_path,
    event_sink=ws_task_panel_sink,                  # D2：推任务面板
)
```

Phase 5 待补：① `resolve_agent`（按名在群内查 Agent）② `event_sink`（事件 → WS 任务面板）③ `available_tools` 是否由 `agent.skills` 映射。

---

## 6. 验收

```bash
V=/home/huishuohuademao/workspace/AgentHub/src/backend/.venv
$V/bin/python -m pytest tests/test_executor.py tests/test_orchestrator.py -q --no-cov
$V/bin/ruff check app/domain/task_engine/executor.py tests/test_executor.py
```

**通过标准**：test_executor 7 用例 + e2e 全绿 + ruff 干净。

---

## 7. 文件增量

| 文件 | 动作 | 行数 |
|------|------|:---:|
| `executor.py` | 新建（build_task_request + AgentExecutor） | ~110 |
| `tests/test_executor.py` | 新建（7 用例 + fake adapter） | ~110 |
| `tests/test_orchestrator.py` | 加 1 个 e2e | +25 |
| `ports.py` / `orchestrator.py` | 不动（Executor Protocol 已定义，依赖注入） |

---

## 关联文档

- [[coordinator-mvp-phase4-executor-spec]] 本相规格 + D1/D2
- [[coordinator-mvp-phase1-orchestrator]] WorkerOutcome / Executor Protocol
- [[coordinator-subsystem-collaborators]] §5.4 Executor / worker=群成员
- [[coordinator-mvp-implementation-plan]] Phase 4 概述
