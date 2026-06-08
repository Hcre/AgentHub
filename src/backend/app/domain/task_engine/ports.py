"""协作者接口与 DTO（coordinator-subsystem-collaborators §5 / coordinator-mvp-phase1-orchestrator）。

可测性接缝（test-plan §0）：Orchestrator 依赖这些 Protocol，测试注入 fake 隔离 LLM/CLI。
Planner=唯一 LLM 协作者；Executor/Verifier=代码（内部包 CLI/命令）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from app.domain.task_engine.dag import TaskDef, TaskNode

# 进度回调（可选注入）：Orchestrator 在 plan/transition 时调，把执行进度推出去。
# (event_type, payload) → 应用层包成 StreamEvent 经 WS 广播。Harness 不依赖 WS/EventBus。
ProgressSink = Callable[[str, dict], Awaitable[None]]

# v4 R4：消息通道（可选注入）。Orchestrator 在关键事件（step 完成/失败/卡死/计划）写 SYSTEM
# 消息到 messages 表 + 广播群聊 → 进 transcript，Planner 和所有 worker 的 CLI session 可见。
# 与 ProgressSink（只推 WS 任务面板）互补：这条入库、进对话上下文。
MessageSink = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class Verdict:
    """Verifier 的裁决——独立于 worker 自报。"""

    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class WorkerOutcome:
    """Executor 跑 worker 的结果（v4：两态 + error）。

    status（详见 coordinator-v4-R1 §8）：
      completed — worker 调了 task_complete，交卷了，ok=True
      not_done  — 流结束未调 task_complete，没交卷（提问/被切断/还在想），ok=True（不是失败）
      error     — worker 自身崩/超时/流错误，ok=False
    """

    ok: bool
    status: Literal["completed", "not_done", "error"] = "completed"
    output: str = ""


class ExitReason(StrEnum):
    COMPLETED = "completed"  # 全部任务 VERIFIED（enum 里是 COMPLETED）
    FAILED = "failed"  # 某任务 retry 耗尽
    UNREACHABLE = "unreachable"  # 下游被 BLOCKED 堵死（无 FAILED 时兜底）
    BUDGET_EXCEEDED = "budget_exceeded"  # 步数上限（防死循环）


@dataclass(frozen=True)
class RunResult:
    reason: ExitReason
    summary: str = ""


@dataclass(frozen=True)
class PlanContext:
    """Planner 分解的输入种子（MVP：gather_context 预注入，不读文件）。"""

    task: str
    workers: tuple[str, ...]  # 可用 worker 名（= group.member_ids，build_graph 校验用）
    repo_tree: str = ""  # 目录树快照（git ls-files / walk）
    constraints: tuple[str, ...] = ()  # 交接硬约束（"错误提示中文"…）
    agents_desc: str = ""  # 成员能力描述（name + capability_tags）
    design_doc: str | None = None  # 用户上传文档（可选）


class TextLLM(Protocol):
    """LLM 文本补全可注入接缝。返回**原始文本**——容错解析归 Planner（§3）。

    不用 chat_structured（它返回 dict 且畸形 JSON 时吞错），否则 Planner 拿不到
    原始文本做容错+重试。真实现包 Anthropic 客户端，返回 content[0].text。
    """

    async def complete(self, prompt: str) -> str: ...


class Planner(Protocol):
    """推理：任务分解。唯一 LLM 协作者（MVP=chat_structured，标准=tool_use 循环）。

    注：MVP 不含 final_answer——末尾汇总由 Harness（Orchestrator）机械生成（成败只锚
    机器判定，零 LLM）。标准档再加 is_request_satisfied 做真正的语义满足判断。
    """

    async def plan(self, ctx: PlanContext) -> list[TaskDef]: ...


class Executor(Protocol):
    """执行：派 worker 跑一个任务，返回结果。内部包 worker CLI。"""

    async def run(self, node: TaskNode) -> WorkerOutcome: ...

    async def abort(self, node_id: str) -> bool:
        """中断在飞 worker（杀进程）。无在飞执行返回 False。"""
        ...

    async def summarize(self, node: TaskNode) -> str:
        """中断后复盘：让 worker --resume 汇报停在哪/做了啥/剩啥/残留。失败返回空串。"""
        ...


class Verifier(Protocol):
    """验收：对完成的任务出裁决。内部跑机械命令 / 独立 reviewer。"""

    async def verify(self, node: TaskNode) -> Verdict: ...
