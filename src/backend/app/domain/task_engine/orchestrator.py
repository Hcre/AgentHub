"""Orchestrator：事件驱动指挥（v4 coordinator-design-v4 §6.2）。

唯一改状态者（单写者）。事件驱动——start/on_feed 为入口，_drive 串行驱动，
无 ready 可派时 break（park）不终止。无轮询。

术语：设计文档的 VERIFIED 终态在 enum 里是 COMPLETED（scheduler 也按 COMPLETED 判依赖满足）。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from app.domain.enums import TaskStatus
from app.domain.task_engine.dag import TaskDef, TaskGraph, TaskNode, build_graph, topological_order
from app.domain.task_engine.fsm import TaskFSM
from app.domain.task_engine.ports import (
    Executor,
    ExitReason,
    MessageSink,
    PlanContext,
    Planner,
    ProgressSink,
    RunResult,
    StallEvent,
    StepEvent,
    Supervisor,
    Verifier,
    WorkerOutcome,
)
from app.domain.task_engine.scheduler import (
    compute_frontier,
    select_dispatchable,
    unreachable_pending,
)

logger = logging.getLogger(__name__)

FinishCallback = Callable[[RunResult], Awaitable[None]]


@dataclass(frozen=True)
class ReplanDiff:
    """replan 影响面（D1：认 workspace 不认节点，不按 id 转移状态）。"""

    running: list[str]    # 旧图在跑/parked（换图会打断、丢 --resume 上下文）
    completed: list[str]  # 旧图已完成（成果保留在 workspace，脱离新计划）
    new_count: int        # 新计划任务数

    @property
    def is_destructive(self) -> bool:
        # D3：只有「打断在跑/parked」才需确认；完成的成果不丢（文件还在），仅信息通报。
        return bool(self.running)


class ReplanNeedsConfirmationError(Exception):
    """破坏性 replan 未确认就 force=False 调用。"""

    def __init__(self, diff: ReplanDiff) -> None:
        super().__init__("replan 破坏性，需用户确认")
        self.diff = diff


def compute_replan_diff(old_graph: TaskGraph, new_tasks: list[TaskDef]) -> ReplanDiff:
    """确定性算影响面（零 LLM）。只读旧图状态，不按 id 匹配。"""
    running = [n.task.id for n in old_graph.nodes.values() if n.status == TaskStatus.RUNNING]
    completed = [n.task.id for n in old_graph.nodes.values() if n.status == TaskStatus.COMPLETED]
    return ReplanDiff(running=running, completed=completed, new_count=len(new_tasks))


def _collect_upstream_summaries(
    node: TaskNode, graph: TaskGraph | None
) -> dict[str, str] | None:
    """收集上游 COMPLETED 节点的 output（task_complete summary），供 worker instruction 注入。

    None = 无上游信息（非空 dict 才注入段，避免空段污染指令）。"""
    if graph is None:
        return None
    summaries = {}
    for dep_id in node.task.depends_on:
        upstream = graph.nodes.get(dep_id)
        if upstream and upstream.status == TaskStatus.COMPLETED and upstream.output:
            summaries[dep_id] = upstream.output
    return summaries or None


class Orchestrator:
    """事件驱动指挥：唯一改状态者。start/on_feed 入口，_drive 串行驱动。"""

    def __init__(
        self,
        *,
        planner: Planner,
        executor: Executor,
        verifier: Verifier,
        ctx: PlanContext,
        progress: ProgressSink | None = None,
        message_sink: MessageSink | None = None,
        supervisor: Supervisor | None = None,
        session_id: UUID | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._verifier = verifier
        self._ctx = ctx
        self._progress = progress
        self._message_sink = message_sink  # R4：关键事件写 transcript（messages 表 + 群聊）
        self._supervisor = supervisor
        self._session_id = session_id
        self.graph: TaskGraph | None = None
        self.events: list[dict] = []  # MVP：内存事件
        # 执行期旁路消息队列（§11.6）：CoordinatorRun 共享此引用，
        # ChatService 调 enqueue_note → 此处 dispatch 前注入 node.pending_notes。
        # v4 R2：按 worker 分桶 dict[worker|"*", list[str]]。
        self._pending_notes: dict[str, list[str]] = {}
        # v4 事件驱动：CoordinatorRun 注入的回调
        self._on_finish: FinishCallback | None = None

    @property
    def parked_step_id(self) -> str | None:
        """串行 MVP：返回唯一 park 节点的 id（RUNNING 但未交卷的 not_done 节点），供 feed 路由。
        R2 Planner decide 后此属性由 caller 提供的 step_id 取代。"""
        if self.graph is None:
            return None
        for node in self.graph.nodes.values():
            if node.status == TaskStatus.RUNNING:
                return node.task.id
        return None

    # ── 事件入口 ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """事件①：任务启动。Planner 建图 → 驱动一次。"""
        defs = await self._planner.plan(self._ctx)
        self.graph = build_graph(defs, set(self._ctx.workers))
        self._record("plan_created", "", n=len(defs))
        await self._emit_plan()
        await self._post_plan()  # R4：计划入 transcript
        await self._drive()

    async def on_feed(self, step_id: str, answer: str) -> None:
        """事件③：用户回话。把答案喂给指定节点，续跑链条。"""
        if self.graph is None:
            return
        node = self.graph.nodes.get(step_id)
        if node is None:
            return

        node.pending_answer = answer

        if node.status == TaskStatus.FAILED:
            # 手动重试：FAILED→PENDING，让 _drive 从 frontier 重捡
            self._transition(node, TaskStatus.PENDING)
            await self._drive()
            return

        # RUNNING（not_done park 中）→ 直接 resume（--resume 续上下文）
        await self._execute_and_settle(node)
        node.pending_answer = None
        await self._drive()

    async def abort_step(self, step_id: str) -> bool:
        """事件④：用户中断某个在飞 worker（杀进程）。节点停在 RUNNING（parked），可续。

        executor.abort 杀进程 → 在飞的 run() 返回 not_done → 驱动任务走 not_done 路径自然 park。
        本方法只负责触发 kill + 标记 + 通报，不直接转状态（保持单写者）。
        返回 False 表示该 step 当前没在飞（无需中断）。"""
        if self.graph is None:
            return False
        node = self.graph.nodes.get(step_id)
        if node is None:
            return False
        if not await self._executor.abort(step_id):
            return False
        node.aborted = True
        worker = node.worker or node.task.suggested_worker
        await self._post_message(
            f"⏹ 已中断【{node.task.title}】（{worker}）。进程已停，节点留存可续"
            "——回它一句新方向即继续，或改计划删掉它。"
        )
        # 复盘：让 worker --resume 汇报停在哪/做了啥/剩啥/残留（不静默）。
        summary = ""
        try:
            summary = await self._executor.summarize(node)
        except Exception:
            logger.exception("复盘失败 task=%s", step_id)
        if summary:
            await self._post_message(f"📋 {worker} 复盘：{summary}")
        else:
            await self._post_message(
                f"（{worker} 没能给出复盘——workspace 可能有未完成改动，建议 git status 自查。）"
            )
        return True

    # ── replan：DAG 手术（design §8）────────────────────────────────────────

    async def abort_inflight(self) -> None:
        """abort 所有在飞 worker（杀进程），供 replan 换图前静默（D2）。
        parked 节点 executor.abort 返回 False，无副作用。"""
        if self.graph is None:
            return
        for node in list(self.graph.nodes.values()):
            if node.status == TaskStatus.RUNNING:
                await self._executor.abort(node.task.id)

    async def plan_replan(self, requirement: str) -> tuple[list[TaskDef], ReplanDiff]:
        """重分解（deliberate 重 LLM）+ 算 diff。只读，不改图。

        已完成的成果喂进 prompt（成果在 workspace，勿重做），让新计划据现状分解（D1）。"""
        assert self.graph is not None
        done = [
            f"- {n.task.title}：{n.output or '已完成'}"
            for n in self.graph.nodes.values() if n.status == TaskStatus.COMPLETED
        ]
        task_text = f"原始任务：{self._ctx.task}\n\n用户新需求：{requirement}"
        if done:
            task_text += "\n\n已完成（成果在 workspace，勿重做）：\n" + "\n".join(done)
        ctx = PlanContext(
            task=task_text, workers=self._ctx.workers,
            repo_tree=self._ctx.repo_tree, constraints=self._ctx.constraints,
            agents_desc=self._ctx.agents_desc,
        )
        new_tasks = await self._planner.plan(ctx)
        return new_tasks, compute_replan_diff(self.graph, new_tasks)

    async def replan(self, new_tasks: list[TaskDef], *, force: bool = False) -> None:
        """原子换图（D1：全新全 PENDING，靠 workspace 持久化）+ 续调度。

        调用方（CoordinatorRun）须先 abort_inflight + 等 drive 收尾再调本方法（D2），
        本方法假设无在飞 worker（不并发改图）。"""
        assert self.graph is not None
        diff = compute_replan_diff(self.graph, new_tasks)
        if diff.is_destructive and not force:
            raise ReplanNeedsConfirmationError(diff)
        self.graph = build_graph(new_tasks, set(self._ctx.workers))
        self._record("replan", "", new=len(new_tasks),
                     was_running=diff.running, was_completed=diff.completed)
        await self._post_plan()
        await self._drive()

    # ── 串行驱动器 ──────────────────────────────────────────────────────────

    async def _drive(self) -> None:
        """串行驱动：派一个 ready → settle → 下一个。
        无 ready 可派时 break（park），不终止、不轮询。"""
        while True:
            assert self.graph is not None
            self._propagate_blocked()
            self._propagate_unblocked()
            ready = select_dispatchable(
                compute_frontier(self.graph), running_count=0, max_concurrency=1
            )
            if not ready:
                break  # ← park：无 PENDING 节点可派
            await self._execute_and_settle(self.graph.nodes[ready[0]])
        await self._check_terminal()

    # ── 单任务执行 + 结算 ──────────────────────────────────────────────────

    async def _execute_and_settle(self, node: TaskNode) -> None:
        """派发一个节点：状态推进 → 执行 → 结算。
        首次派发：PENDING→RUNNING（v4 删 QUEUED 中间态）。
        resume：节点已在 RUNNING（not_done park 中）→ 不转状态，直接续跑。
        """
        if node.status == TaskStatus.PENDING:
            self._transition(node, TaskStatus.RUNNING)
        # else: RUNNING（not_done park 后续跑）→ 不转状态

        if node.worker is None:
            node.worker = node.task.suggested_worker
        # R4：dispatch 前收集上游 COMPLETED 摘要，注入 instruction（§6.7）。
        node.upstream_summaries = _collect_upstream_summaries(node, self.graph)

        # turn-end drain（design §7.3）：每轮跑完先让输出落群聊，再看自己定向桶——
        # 这轮期间又来了本 worker 的消息 → 作为「第二轮对话」续跑注入，桶空才结算。
        # (b)：即便这轮 task_complete 了，桶非空也先续，不结算（验收推迟到桶空）。
        worker = node.task.suggested_worker
        while True:
            node.dispatch_count += 1
            # 自己桶 pop（一次性）+ 全局桶 get（持续，不触发续跑）
            node.pending_notes = (
                self._pending_notes.pop(worker, []) + self._pending_notes.get("*", [])
            )
            await self._emit_update(node, "running")
            outcome = await self._executor.run(node)
            if self._pending_notes.get(worker):  # 仅自己定向桶触发续跑（全局桶不触发）
                continue
            break

        await self._settle(node, outcome)

    async def _settle(self, node: TaskNode, outcome: WorkerOutcome) -> None:
        """结算 worker 产出：completed/not_done/error 三态收敛（v4 coordinator-v4-R1 §2.2）。"""
        if outcome.status == "completed":
            node.output = outcome.output
            self._transition(node, TaskStatus.VERIFYING)
            verdict = await self._verifier.verify(node)
            if verdict.passed:
                self._transition(node, TaskStatus.COMPLETED)
                await self._emit_update(node, "done")
                await self._post_step_done(node)  # R4：完成入 transcript
                await self._notify_supervisor_step_completed(node)
            else:
                permanent = self._handle_failure(node, verdict.reason)
                await self._emit_update(node, "failed", node.fail_reason)
                if permanent:
                    await self._post_step_failed(node)
                    await self._notify_supervisor_step_failed(node)
            return

        if outcome.status == "not_done":
            # 流结束没交卷。不转移、不失败——但主动 nudge worker 调 task_complete。
            # 如果 worker 没提问（无 pending_answer），说明它只是忘了交卷，推一条强制指令。
            worker = node.task.suggested_worker
            if not node.pending_answer and worker:
                self._pending_notes.setdefault(worker, []).append(
                    "你已经完成了所有工作。现在请**只做一件事**：调用 `task_complete` 工具交卷"
                    "（summary 写：做了什么、产物在哪）。不要做其他任何操作，只调工具。"
                )
            self._record("parked", node.task.id)
            return

        # error（worker 崩/超时）→ FAILED + retry
        permanent = self._handle_failure(node, outcome.output or "worker 自身失败/超时")
        await self._emit_update(node, "failed", node.fail_reason)
        if permanent:
            await self._post_step_failed(node)
            await self._notify_supervisor_step_failed(node)

    def _handle_failure(self, node: TaskNode, reason: str) -> bool:
        """处理失败。返回 True 表示永久失败（retry 耗尽/不可重试），调用方据此通报。"""
        node.fail_reason = reason
        self._transition(node, TaskStatus.FAILED)
        node.retries += 1
        if TaskFSM.can_retry(node.retries):
            self._transition(node, TaskStatus.PENDING)  # retry → 回 frontier
            return False  # 还能重试，不通报（内部重试不刷群聊）
        return True  # 永久失败

    # ── 阻塞传播 ────────────────────────────────────────────────────────────

    def _propagate_blocked(self) -> None:
        """PENDING 节点上游不可达 → BLOCKED。"""
        for tid in unreachable_pending(self.graph):
            self._transition(self.graph.nodes[tid], TaskStatus.BLOCKED)

    def _propagate_unblocked(self) -> None:
        """BLOCKED 节点上游全部修复（不再有 FAILED/BLOCKED/CANCELLED）→ PENDING 复活。"""
        assert self.graph is not None
        for node in self.graph.nodes.values():
            if node.status != TaskStatus.BLOCKED:
                continue
            if all(
                self.graph.nodes[dep].status not in (
                    TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.CANCELLED,
                )
                for dep in node.task.depends_on
            ):
                self._transition(node, TaskStatus.PENDING)

    # ── 终态判定（v4：park 不算终态）───────────────────────────────────────

    async def _check_terminal(self) -> None:
        """判定是否真终态。三种结局：
        - 全完成 → _finish（释放 run）
        - FAILED 挡死下游 → 通报卡死（保留 run）
        - 有 park 节点 → 安静返回（保留 run，等 on_feed）
        """
        assert self.graph is not None
        nodes = list(self.graph.nodes.values())

        if all(n.status == TaskStatus.COMPLETED for n in nodes):
            await self._finish(ExitReason.COMPLETED)
            return

        stall = self._detect_stall()
        if stall is not None:
            await self._report_stall(stall)
            return

        # park：有未完成节点但无卡死 → 保留 run，等 on_feed
        return

    def _detect_stall(self) -> str | None:
        """检测永久卡死：FAILED 节点导致下游 BLOCKED，无自动恢复路径。"""
        assert self.graph is not None
        nodes = list(self.graph.nodes.values())
        failed = [n for n in nodes if n.status == TaskStatus.FAILED]
        if not failed:
            return None
        blocked = [n for n in nodes if n.status == TaskStatus.BLOCKED]
        if not blocked:
            # 有 FAILED 但无下游被挡 → 孤立失败，不是卡死
            return None
        failed_ids = [n.task.id for n in failed]
        blocked_ids = [n.task.id for n in blocked]
        return f"任务 {failed_ids} 失败，导致 {blocked_ids} 不可达"

    async def _report_stall(self, description: str) -> None:
        """通报卡死到群聊（不释放 run，等用户决策）。"""
        logger.warning("任务卡死: %s", description)
        content = (
            f"⚠️ 任务卡死：{description}\n"
            "请决定：重试失败任务 / 调整计划 / 结束任务。"
        )
        await self._emit("text", {"content": content})  # WS 任务面板
        await self._post_message(content)                # R4：入 transcript
        # 通知 supervisor
        assert self.graph is not None
        failed_ids = [n.task.id for n in self.graph.nodes.values() if n.status == TaskStatus.FAILED]
        blocked_ids = [n.task.id for n in self.graph.nodes.values() if n.status == TaskStatus.BLOCKED]
        await self._notify_supervisor_stall(description, failed_ids, blocked_ids)

    # ── R4：关键事件入 transcript（messages 表 + 群聊）─────────────────────────

    async def _post_message(self, content: str) -> None:
        if self._message_sink is not None:
            await self._message_sink(content)

    async def _post_plan(self) -> None:
        """任务启动通报：各 step + 依赖拓扑。"""
        assert self.graph is not None
        lines = []
        for n in self.graph.nodes.values():
            deps = ", ".join(n.task.depends_on) if n.task.depends_on else "—"
            lines.append(f"  {n.task.title}（{n.task.suggested_worker}）← {deps}")
        await self._post_message("开始执行：\n" + "\n".join(lines))

    async def _post_step_done(self, node: TaskNode) -> None:
        worker = node.worker or node.task.suggested_worker
        tail = f"\n{node.output}" if node.output else ""
        await self._post_message(f"✅ {node.task.title}（{worker}）已完成{tail}")

    async def _post_step_failed(self, node: TaskNode) -> None:
        worker = node.worker or node.task.suggested_worker
        reason = f"：{node.fail_reason}" if node.fail_reason else ""
        await self._post_message(
            f"❌ {node.task.title}（{worker}）已失败（重试 {node.retries} 次不通过）{reason}"
        )

    # ── Supervisor 通知 ────────────────────────────────────────────────────────

    async def _notify_supervisor_step_completed(self, node: TaskNode) -> None:
        """通知 supervisor 步骤完成。失败静默吞掉，不阻塞主流程。"""
        if self._supervisor is None or self._session_id is None:
            return
        try:
            event = StepEvent(
                step_id=node.task.id,
                title=node.task.title,
                worker=node.worker or node.task.suggested_worker,
                status="completed",
            )
            await self._supervisor.on_step_completed(self._session_id, event)
        except Exception:
            logger.exception("supervisor on_step_completed 异常")

    async def _notify_supervisor_step_failed(self, node: TaskNode) -> None:
        """通知 supervisor 步骤永久失败。失败静默吞掉，不阻塞主流程。"""
        if self._supervisor is None or self._session_id is None:
            return
        try:
            event = StepEvent(
                step_id=node.task.id,
                title=node.task.title,
                worker=node.worker or node.task.suggested_worker,
                status="failed",
                reason=node.fail_reason or "",
            )
            await self._supervisor.on_step_failed(self._session_id, event)
        except Exception:
            logger.exception("supervisor on_step_failed 异常")

    async def _notify_supervisor_all_completed(self) -> None:
        """通知 supervisor 全部完成。"""
        if self._supervisor is None or self._session_id is None:
            return
        try:
            await self._supervisor.on_all_completed(self._session_id)
        except Exception:
            logger.exception("supervisor on_all_completed 异常")

    async def _notify_supervisor_stall(self, description: str, failed: list[str], blocked: list[str]) -> None:
        """通知 supervisor 检测到卡死。"""
        if self._supervisor is None or self._session_id is None:
            return
        try:
            event = StallEvent(
                description=description,
                failed_steps=tuple(failed),
                blocked_steps=tuple(blocked),
            )
            await self._supervisor.on_stall_detected(self._session_id, event)
        except Exception:
            logger.exception("supervisor on_stall_detected 异常")

    async def _finish(self, reason: ExitReason) -> None:
        """全完成：出 summary → 调回调释放 run。"""
        summary = self._build_summary()
        await self._emit_summary(summary)
        if reason == ExitReason.COMPLETED:
            await self._notify_supervisor_all_completed()
        if self._on_finish is not None:
            await self._on_finish(RunResult(reason, summary))

    # ── 机械汇总（B 方案：零 LLM）───────────────────────────────────────────

    def _build_summary(self) -> str:
        nodes = list(self.graph.nodes.values())
        done = sum(n.status == TaskStatus.COMPLETED for n in nodes)
        lines = [f"任务执行结束：{len(nodes)} 个任务，{done} 完成 / {len(nodes) - done} 未完成。"]
        lines.extend(self._summary_line(n) for n in nodes)
        return "\n".join(lines)

    @staticmethod
    def _summary_line(n: TaskNode) -> str:
        accs = [c.spec for c in n.task.acceptance if c.kind == "mechanical"]
        if n.status == TaskStatus.COMPLETED:
            if accs:
                return f"- {n.task.title}：✅ 已完成（验收通过：{'; '.join(accs)}）"
            return f"- {n.task.title}：⚠️ 已完成（未验证：无机器验收，结果未经确认）"
        if n.status == TaskStatus.FAILED:
            reason = f"（原因：{n.fail_reason[:120]}）" if n.fail_reason else ""
            return f"- {n.task.title}：❌ 失败{reason}"
        if n.status == TaskStatus.BLOCKED:
            return f"- {n.task.title}：⏸ 受阻（上游失败导致不可达）"
        if n.status == TaskStatus.CANCELLED:
            return f"- {n.task.title}：🚫 已取消"
        return f"- {n.task.title}：{n.status}"

    # ── 进度推送 ────────────────────────────────────────────────────────────

    async def _emit(self, event_type: str, payload: dict) -> None:
        if self._progress is not None:
            await self._progress(event_type, payload)

    async def _emit_plan(self) -> None:
        assert self.graph is not None
        order = topological_order(self.graph)
        steps = [
            {
                "id": n.task.id,
                "who": n.task.suggested_worker,
                "label": n.task.title,
                "depends": list(n.task.depends_on),
                "status": "pending",
            }
            for tid in order
            if (n := self.graph.nodes.get(tid))
        ]
        await self._emit("task_plan", {"plan": {"summary": "", "steps": steps, "watchouts": []}})

    async def _emit_update(self, node: TaskNode, status: str, reason: str | None = None) -> None:
        payload = {"taskId": node.task.id, "title": node.task.title, "status": status}
        if reason:
            payload["reason"] = reason
        await self._emit("task_update", payload)

    async def _emit_summary(self, summary: str) -> None:
        await self._emit("text", {"content": summary})
        await self._emit("done", {})

    # ── 状态变更（唯一写者）─────────────────────────────────────────────────

    def _transition(self, node: TaskNode, to: TaskStatus) -> None:
        TaskFSM.assert_transition(node.status, to)
        frm, node.status = node.status, to
        self._record("transition", node.task.id, frm=str(frm), to=str(to))

    def _record(self, kind: str, task_id: str, **data: object) -> None:
        self.events.append({"kind": kind, "task": task_id, **data})
