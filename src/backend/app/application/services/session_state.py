"""SessionState — 两条事件流（消息流 + task_events 流）的只读投影（design §3）。

v4 事件驱动版：态由 active_plan 派生——active_plan is None ⟺ 纯对话态；非 None ⟺ 任务在跑。
**无 mode 枚举**。

R2 升级：加 `from_session` 工厂（消息流 + 任务流投影），删 `PlanView.waiting`
（冗余——not_done 节点 = filter(steps, status==running)，无需独立列表）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.entities.agent import Agent
from app.domain.entities.message import Message
from app.domain.repositories import MessageRepository


@dataclass(frozen=True)
class StepView:
    """单个 step 的只读快照（DAG 节点状态投影）。"""

    step_id: str
    worker: str
    status: str  # pending / running / verifying / completed / failed / blocked / cancelled


@dataclass(frozen=True)
class PlanView:
    """active_plan 非空时的 DAG 只读投影。

    v4 R2：无 `waiting` 字段。「谁在等 feed」= filter(steps, status=="running")，
    是 DAG 可确定计算的冗余事实，不需要独立列表（feed 校验直接筛 steps）。
    Planner 据 transcript + 各 step 状态判断用户消息归属。
    """

    steps: tuple[StepView, ...] = ()


@dataclass(frozen=True)
class SessionState:
    """reactive 决策输入。active_plan=None → 纯对话态；非 None → 任务执行态。"""

    session_id: object  # UUID（避免 import 循环，用 object；调用方传 UUID）
    members: tuple[Agent, ...] = ()  # 候选 worker（= 群成员）
    transcript: tuple[Message, ...] = ()  # 近窗口（design §7 reactive 轻档，15 条截断）
    active_plan: PlanView | None = None  # None=纯对话；非 None=DAG 投影
    constraints: tuple[str, ...] = field(default_factory=tuple)

    @property
    def in_execution(self) -> bool:
        """是否处于任务执行态（态由 active_plan 派生，非独立枚举）。"""
        return self.active_plan is not None

    @classmethod
    async def from_session(
        cls,
        *,
        session_id: UUID,
        members: Sequence[Agent],
        message_repo: MessageRepository,
        window: int,
        active_plan: PlanView | None = None,
    ) -> SessionState:
        """从消息流 + 任务流投影构造 reactive 决策输入。

        `active_plan` 由调用方从 CoordinatorRun.plan_view() 取（None=无任务在跑）——
        SessionState 保持纯投影，不反向依赖 CoordinatorRun（避免 import 循环）。
        """
        recent = await message_repo.list_by_session(session_id, limit=window)
        return cls(
            session_id=session_id,
            members=tuple(members),
            transcript=tuple(reversed(recent)),  # 仓库返回倒序 → 翻成时间正序
            active_plan=active_plan,
        )
