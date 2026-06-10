"""Supervisor 决策引擎（域2）：纯函数决策，零 IO、零副作用。

Supervisor 接收结构化事件，产出决策建议（nudge / replan / deploy / 静默）。
决策建议由 SupervisorService（L3）执行——域层只管「该不该做」，不管「怎么发消息/起 CLI」。

设计原则：
  - 纯函数：输入事件 → 输出决策列表，无副作用
  - 可测性：所有决策逻辑独立可测，无需 mock CLI/DB
  - 可配置：阈值/开关通过 SupervisorConfig 控制
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.task_engine.ports import StallEvent, StepEvent, SupervisorConfig


class SupervisorDecisionKind(StrEnum):
    """Supervisor 可做出的决策类型。"""

    NONE = "none"            # 无需行动
    NUDGE = "nudge"          # 轻推某个 worker（"继续干" 或 "交卷"）
    REPLAN = "replan"        # 建议重新分解
    DEPLOY = "deploy"        # 建议部署
    SUMMARIZE = "summarize"  # 产出总结报告
    ALERT = "alert"          # 发出告警消息


@dataclass(frozen=True)
class SupervisorDecision:
    """单条决策建议。"""

    kind: SupervisorDecisionKind
    reason: str = ""
    target_worker: str = ""  # NUDGE 时指定目标 worker
    message: str = ""        # 建议发送给群聊的消息内容
    detail: str = ""         # 补充上下文（如 replan 的需求描述）


@dataclass
class SupervisorState:
    """Supervisor 运行态（纯内存，不持久化）。跟踪已触发的决策避免重复。"""

    completed_count: int = 0
    failed_count: int = 0
    last_nudge_targets: dict[str, int] = field(default_factory=dict)  # worker → 次数
    nudge_count: int = 0         # 本次任务累计 nudge 次数
    replan_count: int = 0        # 本次任务累计 replan 建议次数
    deploy_triggered: bool = False  # 是否已触发过部署


# ── 决策函数 ──────────────────────────────────────────────────────────────────


def decide_on_step_completed(
    event: StepEvent, state: SupervisorState, config: SupervisorConfig
) -> list[SupervisorDecision]:
    """步骤完成时的决策。

    策略：
      - 首个完成 → 静默（稳定推进中）
      - 连续完成 ≥ 3 → 无行动（良好推进）
      - 不做任何自动干涉
    """
    state.completed_count += 1
    # 当前版本：步骤完成时不自动干涉。Supervisor 在 all_completed 才发言。
    return []


def decide_on_step_failed(
    event: StepEvent, state: SupervisorState, config: SupervisorConfig
) -> list[SupervisorDecision]:
    """步骤永久失败（retry 耗尽）时的决策。

    策略：
      - 报告失败信息给群聊
      - 若失败数 ≤ 2 → 提醒用户可重试/改计划
      - 若失败数 ≥ 3 → 建议 replan（可能方向错了）
    """
    state.failed_count += 1
    decisions: list[SupervisorDecision] = []

    decisions.append(
        SupervisorDecision(
            kind=SupervisorDecisionKind.ALERT,
            reason="step_permanent_failure",
            message=(
                f"⚠️ 步骤【{event.title}】（{event.worker}）已失败：{event.reason}。"
            ),
        )
    )

    if state.failed_count >= 3:
        decisions.append(
            SupervisorDecision(
                kind=SupervisorDecisionKind.REPLAN,
                reason=f"累计 {state.failed_count} 个步骤失败，可能方向有误",
                detail=f"已失败 {state.failed_count} 个步骤，建议重新评估计划。最近失败：{event.title}（{event.reason}）",
                message="⚠️ 多个步骤失败，建议调整计划方向。",
            )
        )
    else:
        decisions.append(
            SupervisorDecision(
                kind=SupervisorDecisionKind.NONE,
                reason="awaiting_user_decision",
                message="请决定：重试 / 调整计划 / 继续。",
            )
        )

    return decisions


def decide_on_all_completed(
    completed_count: int, state: SupervisorState, config: SupervisorConfig
) -> list[SupervisorDecision]:
    """全部完成时的决策。

    策略：
      - 产出总结（概要 + 建议下一步）
      - 若配置中启用 deploy → 建议部署
      - 若非首次触发 → 静默（防重复）
    """
    decisions: list[SupervisorDecision] = []

    decisions.append(
        SupervisorDecision(
            kind=SupervisorDecisionKind.SUMMARIZE,
            reason="all_completed",
            message=f"所有 {completed_count} 个任务已完成。",
        )
    )

    # 建议部署（若启用且未触发过）
    if config.enabled and not state.deploy_triggered:
        decisions.append(
            SupervisorDecision(
                kind=SupervisorDecisionKind.DEPLOY,
                reason="all_completed",
                detail="全部任务完成，建议部署变更到线上。",
                message="全部任务完成，建议执行部署。",
            )
        )
        state.deploy_triggered = True

    return decisions


def decide_on_stall(
    event: StallEvent, state: SupervisorState, config: SupervisorConfig
) -> list[SupervisorDecision]:
    """检测到卡死时的决策。

    策略：
      - 告警（说明卡死情况）
      - 若 nudge 次数 < 配置的 max_turns → 建议轻推失败节点
      - 否则 → 建议 replan
    """
    decisions: list[SupervisorDecision] = []

    decisions.append(
        SupervisorDecision(
            kind=SupervisorDecisionKind.ALERT,
            reason="stall_detected",
            message=f"⚠️ {event.description}",
        )
    )

    # 对每个失败节点建议轻推（若还有余量）
    for worker in event.failed_steps:
        if state.nudge_count < config.max_turns:
            decisions.append(
                SupervisorDecision(
                    kind=SupervisorDecisionKind.NUDGE,
                    reason="stall",
                    target_worker=worker,
                    message=f"你的步骤卡住了，请检查是否还需要用户输入。如需调整方向，请在群里说明。",
                )
            )
            state.nudge_count += 1
            state.last_nudge_targets[worker] = state.last_nudge_targets.get(worker, 0) + 1

    # 如果已经 nudge 过多 → 建议 replan
    if state.nudge_count >= config.max_turns:
        decisions.append(
            SupervisorDecision(
                kind=SupervisorDecisionKind.REPLAN,
                reason=f"已 nudge {state.nudge_count} 次仍未恢复，建议重分解",
                detail=f"卡死步骤：{', '.join(event.failed_steps)}。受阻：{', '.join(event.blocked_steps)}。",
                message="⚠️ 多次提醒仍未恢复，建议重新分解任务。",
            )
        )

    return decisions
