"""CoordinatorOrchestrator（L3）：Coordinator 任务分解 + 多 Agent 并行执行 + 失败降级。

依据：
- docs/specs/04-commands §6.2.1 B-2-P2-F01（Orchestrator 失败降级）
- docs/plan/开发清单_roadmap §8.3 P2 缺口「Orchestrator 失败降级」
- docs/specs/01-architecture §3.2 协调者降级路径
- ADR-05（attach 模式：per_agent_status 与 tasks.status 同源更新）

核心流程：
    Given user_message + available_agent_ids
    1. try Coordinator.decompose → 拆解 N 个子任务（PlannedTask）
    2. 并行 dispatch_worker(task, agent) → 每子任务 yield AgentResult
    3. 任一子任务 raise → 标记 status=failed + 不阻塞其他子任务
    4. 全部失败 → 整体降级 manual_mode=True（per Agent 单独 @dispatch）
    5. aggregate → 返回 CoordinatorOutcome

降级矩阵：
    all success   → status="success", degraded=False
    1 fail 降级   → status="partial",  degraded=False（其他子任务继续）
    全 fail       → status="failed",   degraded=True（手动 @Agent 模式）

状态字段（ADR-05 attach 模式）：
    - tasks: list[SubTaskOutcome] (per_subtask: task_id, agent_id, status, output, error)
    - per_agent_status: dict[agent_id, {status, error_code, completed_at}]
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.domain.task_engine.coordinator import Coordinator
from app.domain.task_engine.harness import PlannedTask, TaskPlan

logger = logging.getLogger(__name__)


# --- 状态枚举 ---


class SubTaskStatus(StrEnum):
    """子任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # 降级时不再 dispatch


class CoordinatorStatus(StrEnum):
    """整体协调状态。"""

    SUCCESS = "success"  # 全部子任务成功
    PARTIAL = "partial"  # 部分成功（1 失败但其他完成）
    FAILED = "failed"  # 全部失败（触发降级）
    DECOMPOSE_FAILED = "decompose_failed"  # 任务分解本身失败（LLM/parse 错）


# --- 数据结构 ---


@dataclass
class SubTaskOutcome:
    """单个子任务的执行结果。"""

    task_id: UUID
    title: str
    agent_id: UUID | None
    status: SubTaskStatus = SubTaskStatus.PENDING
    output: str = ""
    error_code: str | None = None
    error_message: str | None = None
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def duration_ms(self) -> int:
        if self.started_at is None or self.completed_at is None:
            return 0
        return int((self.completed_at - self.started_at) * 1000)


@dataclass
class CoordinatorOutcome:
    """协调器整体结果。"""

    status: CoordinatorStatus = CoordinatorStatus.SUCCESS
    degraded: bool = False  # True → 手动 @Agent 模式
    mode: str = "auto"  # "auto" | "manual"
    plan_rationale: str = ""
    tasks: list[SubTaskOutcome] = field(default_factory=list)
    per_agent_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    summary: str = ""
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == SubTaskStatus.FAILED)

    @property
    def success_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == SubTaskStatus.SUCCESS)


# --- Worker 抽象：注入 dispatch 函数（解耦 LLM 适配器） ---


# worker_dispatch(task, agent_id) -> output_string
WorkerDispatch = Callable[[PlannedTask, UUID], Awaitable[str]]


# --- 核心实现 ---


class CoordinatorOrchestrator:
    """L3 协调器：任务拆解 + 并行执行 + 失败降级。

    用法：
        orch = CoordinatorOrchestrator(coordinator, worker_dispatch=my_dispatch)
        outcome = await orch.run(user_message, agent_ids=[...])
        # outcome.tasks: per_subtask
        # outcome.per_agent_status: per_agent
    """

    def __init__(
        self,
        coordinator: Coordinator,
        *,
        worker_dispatch: WorkerDispatch,
    ) -> None:
        self._coordinator = coordinator
        self._dispatch = worker_dispatch

    async def run(
        self,
        user_message: str,
        *,
        agent_ids: list[UUID],
        agent_names: dict[UUID, str] | None = None,
        timeout_per_task: float = 30.0,
    ) -> CoordinatorOutcome:
        """执行完整协调流程。

        Args:
            user_message: 用户消息原文
            agent_ids: 群组可用 Agent id 列表
            agent_names: agent_id → name 映射（路由用，缺省则用空字符串）
            timeout_per_task: 单子任务超时秒数

        Returns:
            CoordinatorOutcome（含 per_task 状态 + per_agent 状态）
        """
        outcome = CoordinatorOutcome(started_at=time.time())
        name_map = agent_names or {}

        # 阶段 1：任务分解（try/except 包裹 — 失败 → 降级）
        try:
            plan = await self._decompose(user_message, agent_ids, name_map)
            outcome.plan_rationale = plan.rationale
            outcome.mode = "auto"
        except Exception as exc:
            logger.exception("Coordinator 任务分解失败，降级为手动 @Agent 模式")
            return self._build_degraded_outcome(
                outcome, user_message, agent_ids, name_map, exc
            )

        # 阶段 2：路由 + 初始化 outcomes
        outcomes = self._route(plan, agent_ids, name_map)
        outcome.tasks = outcomes

        # 阶段 3：并行执行（asyncio.gather + return_exceptions=True）
        await self._run_parallel(outcomes, timeout_per_task=timeout_per_task)

        # 阶段 4：聚合 per_agent_status（ADR-05 attach 模式）
        outcome.per_agent_status = self._aggregate_per_agent(outcomes)
        outcome.completed_at = time.time()

        # 阶段 5：判定整体 status
        n_success = sum(1 for o in outcomes if o.status == SubTaskStatus.SUCCESS)
        n_failed = sum(1 for o in outcomes if o.status == SubTaskStatus.FAILED)

        if n_failed == 0:
            outcome.status = CoordinatorStatus.SUCCESS
            outcome.degraded = False
            outcome.summary = f"全部 {n_success} 个子任务成功"
        elif n_success == 0:
            # 全部失败 → 整体降级为手动模式
            outcome.status = CoordinatorStatus.FAILED
            outcome.degraded = True
            outcome.mode = "manual"
            outcome.summary = (
                f"全部 {n_failed} 个子任务失败；降级为手动 @Agent 模式，"
                "请用户手动指定 Agent 重试"
            )
        else:
            outcome.status = CoordinatorStatus.PARTIAL
            outcome.degraded = False
            outcome.summary = (
                f"{n_success} 成功 / {n_failed} 失败；"
                "失败子任务已记录，可重试或忽略"
            )

        return outcome

    # --- 私有方法 ---

    async def _decompose(
        self,
        user_message: str,
        agent_ids: list[UUID],
        name_map: dict[UUID, str],
    ) -> TaskPlan:
        """调用 Coordinator 拆解任务。"""
        names = [name_map.get(aid, str(aid)) for aid in agent_ids]
        return await self._coordinator.decompose(
            message=user_message,
            available_agents=names,
        )

    def _route(
        self,
        plan: TaskPlan,
        agent_ids: list[UUID],
        name_map: dict[UUID, str],
    ) -> list[SubTaskOutcome]:
        """将 PlannedTask 路由到具体 Agent id（轮询分配）。"""
        outcomes: list[SubTaskOutcome] = []
        available = list(agent_ids)
        if not available:
            # 边界：无可用 Agent → 全部 SKIPPED
            for t in plan.tasks:
                outcomes.append(
                    SubTaskOutcome(
                        task_id=uuid4(),
                        title=t.title,
                        agent_id=None,
                        status=SubTaskStatus.SKIPPED,
                        error_code="E_NO_AGENT",
                        error_message="无可用 Agent",
                    )
                )
            return outcomes

        for i, task in enumerate(plan.tasks):
            target_id = available[i % len(available)]
            outcomes.append(
                SubTaskOutcome(
                    task_id=uuid4(),
                    title=task.title,
                    agent_id=target_id,
                )
            )
        return outcomes

    async def _run_parallel(
        self,
        outcomes: list[SubTaskOutcome],
        *,
        timeout_per_task: float,
    ) -> None:
        """并行执行所有子任务，单个失败不阻塞其他。"""
        tasks: list[asyncio.Task[None]] = []

        async def _run_one(out: SubTaskOutcome) -> None:
            assert out.agent_id is not None  # 路由时已确保
            out.status = SubTaskStatus.RUNNING
            out.started_at = time.time()
            try:
                # 构造一个最小 PlannedTask（仅用于 dispatch 签名兼容）
                planned = PlannedTask(
                    title=out.title,
                    description="",
                    suggested_worker="",
                )
                out.output = await asyncio.wait_for(
                    self._dispatch(planned, out.agent_id),
                    timeout=timeout_per_task,
                )
                out.status = SubTaskStatus.SUCCESS
            except TimeoutError:
                out.status = SubTaskStatus.FAILED
                out.error_code = "E_TASK_TIMEOUT"
                out.error_message = f"子任务超时（>{timeout_per_task}s）"
                logger.warning("子任务 %s 超时", out.task_id)
            except Exception as exc:
                out.status = SubTaskStatus.FAILED
                out.error_code = type(exc).__name__
                out.error_message = str(exc)
                logger.warning("子任务 %s 失败：%s", out.task_id, exc)
            finally:
                out.completed_at = time.time()

        for o in outcomes:
            if o.status == SubTaskStatus.SKIPPED:
                continue  # 跳过无可用 Agent 的子任务
            tasks.append(asyncio.create_task(_run_one(o)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _aggregate_per_agent(
        self, outcomes: list[SubTaskOutcome]
    ) -> dict[str, dict[str, Any]]:
        """按 agent_id 聚合状态（ADR-05 attach 模式）。"""
        agg: dict[str, dict[str, Any]] = {}
        for o in outcomes:
            if o.agent_id is None:
                continue
            key = str(o.agent_id)
            bucket = agg.setdefault(
                key,
                {
                    "agent_id": key,
                    "task_count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "status": "ok",
                    "error_codes": [],
                    "last_completed_at": None,
                },
            )
            bucket["task_count"] += 1
            if o.status == SubTaskStatus.SUCCESS:
                bucket["success_count"] += 1
            elif o.status == SubTaskStatus.FAILED:
                bucket["failed_count"] += 1
                if o.error_code:
                    bucket["error_codes"].append(o.error_code)
            elif o.status == SubTaskStatus.SKIPPED:
                bucket["skipped_count"] += 1
            if o.completed_at and (
                bucket["last_completed_at"] is None
                or o.completed_at > bucket["last_completed_at"]
            ):
                bucket["last_completed_at"] = o.completed_at

        # 整体 status
        for bucket in agg.values():
            if bucket["failed_count"] > 0 and bucket["success_count"] > 0:
                bucket["status"] = "partial"
            elif bucket["failed_count"] > 0:
                bucket["status"] = "failed"
            elif bucket["skipped_count"] == bucket["task_count"]:
                bucket["status"] = "skipped"
            else:
                bucket["status"] = "ok"
        return agg

    def _build_degraded_outcome(
        self,
        outcome: CoordinatorOutcome,
        user_message: str,
        agent_ids: list[UUID],
        name_map: dict[UUID, str],
        exc: Exception,
    ) -> CoordinatorOutcome:
        """降级为手动 @Agent 模式：原消息不动，提示用户手动 @Agent 重试。"""
        outcome.status = CoordinatorStatus.DECOMPOSE_FAILED
        outcome.degraded = True
        outcome.mode = "manual"
        outcome.completed_at = time.time()
        outcome.summary = (
            f"任务分解失败（{type(exc).__name__}: {exc}）；"
            "已降级为手动 @Agent 模式，请用户手动指定 Agent 重试"
        )
        # 创建一个 dummy 子任务代表"原始用户消息"
        for aid in agent_ids:
            outcome.tasks.append(
                SubTaskOutcome(
                    task_id=uuid4(),
                    title=f"[手动 @Agent] {user_message[:60]}",
                    agent_id=aid,
                    status=SubTaskStatus.SKIPPED,
                    error_code="E_DECOMPOSE_FAILED",
                    error_message=f"任务分解失败：{exc}",
                )
            )
        outcome.per_agent_status = self._aggregate_per_agent(outcome.tasks)
        return outcome


__all__ = [
    "CoordinatorOrchestrator",
    "CoordinatorOutcome",
    "CoordinatorStatus",
    "SubTaskOutcome",
    "SubTaskStatus",
    "WorkerDispatch",
]
