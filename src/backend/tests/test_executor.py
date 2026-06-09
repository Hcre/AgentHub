"""Executor 测试（coordinator-test-plan §Executor）。fake adapter，不起真 CLI。
v4 R1 适配：删 ask tool 测试，needs_reprompt→not_done(ok=True)，TEXT 推 sink。"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.domain.entities.agent import Agent
from app.domain.llm.protocol import StreamEvent, StreamEventType, ToolCall
from app.domain.task_engine.dag import Check, TaskDef, TaskNode
from app.domain.task_engine.executor import (
    _TASK_COMPLETE_TOOL,
    AgentExecutor,
    build_task_request,
)


def _agent(name="前端Agent") -> Agent:
    return Agent(name=name, avatar="x", role="dev")


def _node(worker="前端Agent") -> TaskNode:
    task = TaskDef(id="t1", title="建页面", suggested_worker=worker,
                   acceptance=[Check("mechanical", "true")])
    return TaskNode(task=task)


def _evt(t, content=None, seq=0) -> StreamEvent:
    return StreamEvent(type=t, seq=seq, content=content)


def _tool_evt(name, args, seq=0) -> StreamEvent:
    return StreamEvent(
        type=StreamEventType.TOOL_CALL, seq=seq,
        tool_call=ToolCall(call_id="c", name=name, arguments=args),
    )


class FakeAdapter:
    """yield 预设事件序列；slow>0 时每个事件前 sleep（测超时）。"""

    def __init__(self, events, slow: float = 0.0):
        self._events = events
        self._slow = slow

    async def stream(self, request):
        for e in self._events:
            if self._slow:
                await asyncio.sleep(self._slow)
            yield e


def _exec(adapter, resolve=None, timeout=2.0, event_sink=None) -> AgentExecutor:
    return AgentExecutor(
        resolve_agent=resolve or (lambda name: _agent(name)),
        adapter_factory=lambda agent: adapter,
        session_id=uuid4(), group_id=uuid4(), workspace="/tmp",
        timeout=timeout, event_sink=event_sink,
    )


@pytest.mark.asyncio
async def test_task_complete_marks_completed():
    """调 task_complete → WorkerOutcome(completed)，output=summary。"""
    adapter = FakeAdapter([
        _evt(StreamEventType.THINKING, "想"),
        _evt(StreamEventType.TEXT, "创建了 LoginForm.tsx"),
        _tool_evt(_TASK_COMPLETE_TOOL, {"summary": "建好了 LoginForm.tsx"}),
        _evt(StreamEventType.DONE),
    ])
    result = await _exec(adapter).run(_node())
    assert result.ok
    assert result.status == "completed"
    assert "LoginForm" in result.output


@pytest.mark.asyncio
async def test_no_terminator_not_done():
    """只输出文本不调 task_complete → not_done（ok=True，不是失败）。"""
    adapter = FakeAdapter([
        _evt(StreamEventType.TEXT, "创建了 LoginForm.tsx"),
        _evt(StreamEventType.TEXT, "但还需要确认样式……"),
        _evt(StreamEventType.DONE),
    ])
    result = await _exec(adapter).run(_node())
    assert result.ok  # v4: not_done 不是失败
    assert result.status == "not_done"


@pytest.mark.asyncio
async def test_non_step_tool_calls_ignored():
    """Read/Bash 等非 task_complete 工具调用被忽略，最终仍 not_done。"""
    adapter = FakeAdapter([
        _tool_evt("Read", {"file_path": "/x"}),
        _tool_evt("Bash", {"command": "ls"}),
        _evt(StreamEventType.TEXT, "看了文件"),
        _evt(StreamEventType.DONE),
    ])
    result = await _exec(adapter).run(_node())
    assert result.status == "not_done"


@pytest.mark.asyncio
async def test_text_events_pushed_to_sink():
    """v4: TEXT 事件经 event_sink 推群聊，不再吞入 buffer。"""
    seen: list[StreamEvent] = []

    async def sink(evt: StreamEvent) -> None:
        seen.append(evt)

    adapter = FakeAdapter([
        _evt(StreamEventType.TEXT, "我先看看……"),
        _tool_evt(_TASK_COMPLETE_TOOL, {"summary": "done"}),
        _evt(StreamEventType.DONE),
    ])
    await _exec(adapter, event_sink=sink).run(_node())
    # TEXT 推 sink 且被标记 sender（谁在说话）；turn 结束保证有 DONE flush。
    text_evts = [e for e in seen if e.type == StreamEventType.TEXT]
    assert text_evts and "先看看" in (text_evts[0].content or "")
    assert text_evts[0].sender_agent_id is not None  # 标了 worker 身份
    assert any(e.type == StreamEventType.DONE for e in seen)  # turn 结束 flush


@pytest.mark.asyncio
async def test_worker_text_persisted_via_sink_on_done():
    """make_worker_event_sink：累积 TEXT，DONE 时落成一条 worker 消息（注入 fake persist）。"""
    from app.application.services.coordinator_run import make_worker_event_sink

    persisted: list[tuple[object, str]] = []

    async def fake_persist(agent_id, text):  # type: ignore[no-untyped-def]
        persisted.append((agent_id, text))

    sink = make_worker_event_sink(uuid4(), persist=fake_persist)
    aid = uuid4()
    await sink(StreamEvent(type=StreamEventType.TEXT, seq=0, content="用 Markdown ", sender_agent_id=aid))
    await sink(StreamEvent(type=StreamEventType.TEXT, seq=1, content="还是 CMS?", sender_agent_id=aid))
    assert persisted == []  # 还没 DONE，不落
    await sink(StreamEvent(type=StreamEventType.DONE, seq=2, sender_agent_id=aid))
    assert persisted == [(aid, "用 Markdown 还是 CMS?")]  # DONE 整条落库


@pytest.mark.asyncio
async def test_worker_not_found():
    result = await _exec(FakeAdapter([]), resolve=lambda name: None).run(_node())
    assert not result.ok
    assert "worker 不存在" in result.output


@pytest.mark.asyncio
async def test_stream_error_fails():
    result = await _exec(FakeAdapter([_evt(StreamEventType.ERROR, "CLI 崩了")])).run(_node())
    assert not result.ok
    assert "报错" in result.output


@pytest.mark.asyncio
async def test_approval_blocks():
    result = await _exec(FakeAdapter([_evt(StreamEventType.REQUEST_APPROVAL, "需批准")])).run(_node())
    assert not result.ok
    assert "审批" in result.output


@pytest.mark.asyncio
async def test_timeout_fails():
    adapter = FakeAdapter([_evt(StreamEventType.TEXT, "慢")] * 10, slow=1.0)
    result = await _exec(adapter, timeout=0.5).run(_node())
    assert not result.ok
    assert "超时" in result.output


@pytest.mark.asyncio
async def test_adapter_raises_caught():
    class BoomAdapter:
        async def stream(self, request):
            if True:
                raise RuntimeError("boom")
            yield StreamEvent(type=StreamEventType.DONE, seq=0)

    result = await _exec(BoomAdapter()).run(_node())
    assert not result.ok
    assert "执行失败" in result.output


# --- §11.6 执行期旁路消息队列 ---


def test_pending_notes_injected_into_instruction():
    """node.pending_notes → instruction 加「用户执行期补充」段。"""
    node = _node()
    node.pending_notes = ["请使用 React", "错误提示中文"]
    request = build_task_request(
        node, _agent(), session_id=uuid4(), group_id=uuid4(), workspace="/tmp"
    )
    body = request.messages[0]["content"]
    assert "React" in body
    assert "中文" in body
    assert "用户执行期补充" in body


def test_pending_notes_empty_no_segment():
    """node.pending_notes=None 时不注入多余段落。"""
    node = _node()
    node.pending_notes = None
    request = build_task_request(
        node, _agent(), session_id=uuid4(), group_id=uuid4(), workspace="/tmp"
    )
    assert "用户执行期补充" not in request.messages[0]["content"]


# --- 中断复盘 ---


@pytest.mark.asyncio
async def test_summarize_collects_text():
    """summarize → --resume 让 worker 汇报，收集 TEXT 文本返回。"""
    adapter = FakeAdapter([
        _evt(StreamEventType.TEXT, "停在写 LoginForm，"),
        _evt(StreamEventType.TEXT, "样式还没做，有半截 tsx。"),
        _evt(StreamEventType.DONE),
    ])
    summary = await _exec(adapter).summarize(_node())
    assert "LoginForm" in summary and "样式" in summary


def test_build_summary_request_resumes():
    """复盘请求 has_history=True（--resume 复原上下文）+ 含「中止」提示。"""
    from app.domain.task_engine.executor import build_summary_request
    req = build_summary_request(
        _node(), _agent(), session_id=uuid4(), group_id=uuid4(), workspace="/tmp"
    )
    assert req.has_history is True
    assert "中止" in req.messages[0]["content"]
