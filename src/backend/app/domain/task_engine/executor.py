"""Executor — 派群成员 Agent 执行任务（coordinator-mvp-phase4-executor-spec §1）。

代码（非 LLM）：解析 worker → 构造任务请求（D1）→ adapter.stream → 收流 → WorkerOutcome。
永不抛异常给 Orchestrator——所有失败收敛成 WorkerOutcome(ok=False)（spec §3）。
worker 流事件 → event_sink（D2，任务面板；MVP 默认 no-op）。

worker = 群成员 Agent；复用 build_adapter_for_agent + adapter.stream（不新建 CLI 管道）。
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

DEFAULT_TIMEOUT = 600.0  # 单任务墙钟上限（秒）；__init__ 的 timeout 参可覆盖

# step-tools MCP 终结工具名（Claude Code CLI 格式：mcp__<server>__<tool>）
# server name 来自 mcp_step_tools.py 的 FastMCP("agenthub-step-tools")
# 若实测格式不同，只改此处常量即可
_TASK_COMPLETE_TOOL = "mcp__agenthub-step-tools__task_complete"

# 任务执行契约（D1：不是群聊回复，是"干这个活"）。
# v4 完成协议（coordinator-v4-R1 §6.4）：task_complete 是唯一结构化信号。
# worker 说话走正常 TEXT 推群聊；流结束没调 task_complete = not_done（没交卷，不是失败）。
TASK_EXEC_CONTRACT = (
    "你被分配了一个具体任务。请直接完成它（写代码/改文件/跑命令），不要闲聊或只回复。"
    "严格遵守下方约束与验收标准。\n\n"
    "完成后必须调用 `task_complete` 工具，summary 说明：做了什么、产物在哪、关键决策。\n"
    "如果信息不全、需要确认或等待回复，直接以文本说出来然后结束——"
    "不要凭猜测推进，用户看到后会回复你。"
)

ResolveAgent = Callable[[str], Agent | None]
AdapterFactory = Callable[[Agent], object]  # 返回有 .stream(request) 的 UnifiedAgent
EventSink = Callable[[StreamEvent], Awaitable[None]]  # async（D2 推面板）

# 中断后复盘提示（worker --resume 后用）：只汇报不动手。
_ABORT_SUMMARY_PROMPT = (
    "你被用户中止了，现在停手，不要再做任何修改/写文件/跑命令"
    "（只读地跑 `git status` 看现状可以）。用简短几句在群里说明："
    "你停在哪一步、已经做了什么、还剩什么没做、workspace 有什么残留。"
)


def build_task_instruction(node: TaskNode) -> str:
    """TaskDef → 任务指令文本（D1）。

    v4 R4：注入上游 COMPLETED 节点的 task_complete summary（§6.7）——B 依赖 A 时，
    B 的指令里能看到 A 做了什么、产物在哪，不用自己读文件猜。
    """
    t = node.task
    parts = [f"# 任务：{t.title}", t.description or ""]
    if node.upstream_summaries:
        parts.append(
            "## 上游任务完成摘要\n"
            + "\n".join(f"- {tid}：{summary}" for tid, summary in node.upstream_summaries.items())
        )
    mech = [c.spec for c in t.acceptance if c.kind == "mechanical"]
    if mech:
        parts.append(
            "## 验收（你的产出必须让这些命令通过）\n"
            + "\n".join(f"- `{s}`" for s in mech)
        )
    return "\n\n".join(p for p in parts if p)


def build_task_request(
    node: TaskNode, agent: Agent, *, session_id: UUID, group_id: UUID, workspace: str | None
) -> AgentRequest:
    """构造任务执行请求（D1：指令做 content，任务契约做 sp，非群聊回复）。

    首次派发：指令做 content，has_history=False（CLI --session-id 新建）。
    resume 派发（node.pending_answer 非空）：注入用户回答做 content，has_history=True
      → CLI --resume 复原上次对话上下文（含 ask 时的进度），worker 接着干。
      session_key 由 ClaudeCodeRuntime 按 (session_id, agent_id) 确定性计算，
      同一 worker resume 同一会话天然命中，无需额外传 step_key（MVP 串行保证单活跃 step）。
    """
    system_prompt = "\n\n".join(filter(None, [agent.system_prompt, TASK_EXEC_CONTRACT]))
    # 始终 --resume：Agent 在群聊 relay 时已有 CLI session，coordinator 任务续进去投放，
    # 不另建 session（避免 "Session ID already in use" 冲突）。
    # 若 session 还未创建（首次），runtime 自带 fallback 新建。
    has_pending = node.pending_answer is not None
    if has_pending:
        content = (
            f"针对你之前的问题，用户回复如下：\n\n{node.pending_answer}\n\n"
            "请基于此回复继续完成任务。完成后调用 task_complete；仍需确认则直接以文本说出来再结束。"
        )
    else:
        content = build_task_instruction(node)
    notes = node.pending_notes or []
    if notes:
        content += "\n\n## 用户执行期补充（请注意以下约束）\n" + "\n".join(f"- {n}" for n in notes)
    return AgentRequest(
        request_id=str(uuid4()),
        session_id=session_id,
        messages=[{"role": "user", "content": content}],
        system_prompt=system_prompt,
        available_tools=[],  # CLI 运行时忽略此字段，CLI 自带全工具；仅 API adapter 用它
        working_directory=node.worktree or workspace,
        agent_id=agent.id,
        group_id=group_id,
        is_group_chat=True,
        has_history=True,  # 始终 --resume：投放任务到已有 CLI session，不新建冲突
    )


def build_summary_request(
    node: TaskNode, agent: Agent, *, session_id: UUID, group_id: UUID, workspace: str | None
) -> AgentRequest:
    """中断复盘请求：--resume 复原被中断前上下文，让 worker 汇报停在哪/做了啥/剩啥/残留。"""
    return AgentRequest(
        request_id=str(uuid4()),
        session_id=session_id,
        messages=[{"role": "user", "content": _ABORT_SUMMARY_PROMPT}],
        system_prompt=agent.system_prompt or "",
        available_tools=[],
        working_directory=node.worktree or workspace,
        agent_id=agent.id,
        group_id=group_id,
        is_group_chat=True,
        has_history=True,  # --resume 复原中断前的上下文
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
        # 在飞 adapter 注册表（node_id → adapter），供 abort 中途 stop（杀进程）。
        self._inflight: dict[str, object] = {}

    async def run(self, node: TaskNode) -> WorkerOutcome:
        agent = self._resolve(node.task.suggested_worker)
        if agent is None:
            return WorkerOutcome(ok=False, status="error", output=f"worker 不存在: {node.task.suggested_worker}")

        request = build_task_request(
            node, agent, session_id=self._session_id,
            group_id=self._group_id, workspace=self._workspace,
        )
        adapter = self._adapter_factory(agent)
        self._inflight[node.task.id] = adapter
        try:
            return await asyncio.wait_for(
                self._consume(adapter, request, node), timeout=self._timeout
            )
        except TimeoutError:
            logger.warning("worker 执行超时 task=%s", node.task.id)
            return WorkerOutcome(ok=False, status="error", output=f"执行超时（>{self._timeout}s）")
        except Exception as exc:  # 流崩/CLI 错 → 收敛，不抛给 Orchestrator
            logger.exception("worker 执行失败 task=%s", node.task.id)
            return WorkerOutcome(ok=False, status="error", output=f"执行失败: {exc}")
        finally:
            self._inflight.pop(node.task.id, None)

    async def abort(self, node_id: str) -> bool:
        """中断在飞 worker：stop() 杀进程 → stream 结束 → run 返回 not_done（节点 park）。
        返回 False 表示该节点当前没有在飞执行。"""
        adapter = self._inflight.get(node_id)
        if adapter is None:
            return False
        stop = getattr(adapter, "stop", None)
        if stop is not None:
            await stop()
        return True

    async def summarize(self, node: TaskNode) -> str:
        """中断后复盘：--resume 让 worker 汇报停在哪/做了啥/剩啥/残留。返回汇报文本（失败→空）。

        进程已被 abort 杀掉，这里 spawn 一个新的 --resume turn 复原上下文。session 文件
        若被强杀损坏 → --resume fallback（runtime 内部处理），上下文可能丢，汇报会泛化——
        调用方据空串走机械兜底。
        """
        agent = self._resolve(node.task.suggested_worker)
        if agent is None:
            return ""
        request = build_summary_request(
            node, agent, session_id=self._session_id,
            group_id=self._group_id, workspace=self._workspace,
        )
        adapter = self._adapter_factory(agent)
        try:
            return await asyncio.wait_for(self._collect_text(adapter, request), timeout=self._timeout)
        except Exception:
            logger.exception("复盘 summarize 失败 task=%s", node.task.id)
            return ""

    async def _collect_text(self, adapter: object, request: AgentRequest) -> str:
        """消费流，收集 TEXT 文本。供 summarize 用——输出由 orchestrator 单独发（不走 event_sink，
        避免与「📋 复盘」双重）。"""
        chunks: list[str] = []
        async for evt in adapter.stream(request):  # type: ignore[attr-defined]
            if evt.type == StreamEventType.TEXT and evt.content:
                chunks.append(evt.content)
        return "".join(chunks).strip()

    async def _to_sink(self, evt: StreamEvent, agent_id: object) -> None:
        """推 event_sink，给未标记的事件补上 worker 的 sender_agent_id（谁在说话）。"""
        if self._sink is None:
            return
        if evt.sender_agent_id is None:
            evt = evt.model_copy(update={"sender_agent_id": agent_id})
        await self._sink(evt)

    async def _consume(self, adapter: object, request: AgentRequest, node: TaskNode) -> WorkerOutcome:
        """消费事件流，检测 task_complete 终结工具调用（v4 coordinator-v4-R1 §2.1）。

        终结逻辑：
          - TOOL_CALL name==task_complete → WorkerOutcome(completed)
          - 流结束但无 task_complete       → WorkerOutcome(not_done)，ok=True（没交卷，不是失败）
        worker 说话（TEXT）经 event_sink 推群聊（标 sender=worker）。turn 结束保证发一个 DONE 让
        sink flush 累积文本成一条 worker 消息进 transcript（即便流没自带 DONE/提前 error）。

        ⚠ tool name 格式已确认为 mcp__<server>__<tool>（Claude Code CLI 标准行为）。
        """
        done_summary: str | None = None
        try:
            async for evt in adapter.stream(request):  # type: ignore[attr-defined]
                await self._to_sink(evt, request.agent_id)  # TEXT 进群聊（sink 累积/flush）
                if evt.type == StreamEventType.TOOL_CALL and evt.tool_call:
                    if evt.tool_call.name == _TASK_COMPLETE_TOOL:
                        done_summary = evt.tool_call.arguments.get("summary", "")
                        logger.info("task_complete detected task=%s", node.task.id)
                elif evt.type == StreamEventType.ERROR:
                    return WorkerOutcome(
                        ok=False, status="error",
                        output=f"worker 报错: {evt.content or 'worker error'}",
                    )
                elif evt.type == StreamEventType.REQUEST_APPROVAL:
                    return WorkerOutcome(ok=False, status="error", output="worker 需要审批（MVP 不支持）")
        finally:
            # 保证 sink 收到 DONE flush 本轮文本（正常流自带 DONE 时此处 buffer 已空，无副作用）。
            await self._to_sink(StreamEvent(type=StreamEventType.DONE, seq=0), request.agent_id)

        if done_summary is not None:
            return WorkerOutcome(ok=True, status="completed", output=done_summary)
        # 流结束没调 task_complete → not_done。不是失败——worker 可能在等回复或被切断。
        return WorkerOutcome(
            ok=True, status="not_done",
            output="worker 未调用 task_complete（流结束未交卷）",
        )
