"""DAG 模型与校验（coordinator-dag-driven-design-v2 §8 / §2.1）。

纯领域逻辑，无 IO、无 LLM。Coordinator 产出 list[TaskDef]，build_graph 校验后
编译为 TaskGraph。调度（frontier）见同模块；校验只挡结构错误，不判 LLM 智商。

校验项（coordinator-test-plan §1）：
- 重复 id / 悬空依赖 / 未知 worker / 无 acceptance 且未标 no_verify / 循环依赖
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.exceptions import DomainError
from app.domain.enums import TaskStatus

SideEffectLevel = Literal["none", "readonly", "mutable", "external"]
CheckKind = Literal["mechanical", "llm_judge", "human"]

# DFS 环检测的着色状态
_UNVISITED, _IN_STACK, _DONE = 0, 1, 2


class DagValidationError(DomainError):
    """Coordinator 产出的 DAG 结构非法（环/悬空/未知 worker/无验收等）。"""


@dataclass(frozen=True)
class Check:
    """单条验收标准。mechanical=Harness 跑命令；llm_judge=独立 reviewer；human=人工。"""

    kind: CheckKind
    spec: str  # mechanical: 命令；llm_judge: 评审标准；human: 提示
    expect: str | None = None  # mechanical: 期望退出码/输出


@dataclass
class TaskDef:
    """Coordinator 产出的子任务定义（plan 阶段，校验前）。"""

    id: str
    title: str
    suggested_worker: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    acceptance: list[Check] = field(default_factory=list)
    side_effect_level: SideEffectLevel = "readonly"
    no_verify: bool = False  # 显式声明"无需验证"，否则空 acceptance = 校验失败
    expandable: bool = False  # 完成时触发动态扩图（§2.7）
    input_template: str | None = None  # 动态输入占位（§2.4）


@dataclass
class TaskNode:
    """DAG 执行节点（运行态投影，可变）。"""

    task: TaskDef
    status: TaskStatus = TaskStatus.PENDING
    worker: str | None = None
    worktree: str | None = None  # 标准档每 task 独立 worktree；MVP 串行为 None，Verifier 回退 workspace
    output: str | None = None
    fail_reason: str | None = None
    retries: int = 0
    # 协调者 v3 ask/resume 多轮对话状态：
    step_key: str | None = None  # uuid5(session_id, task_id)，CLI session 隔离 + resume 锚点
    dispatch_count: int = 0  # 派发次数（含 resume）；超限防 ask 死循环
    pending_answer: str | None = None  # waiting 期间收到的用户回答，resume 时注入
    pending_notes: list[str] | None = None  # 执行期旁路消息队列，dispatch 前注入 instruction
    # v4 R4：上游 COMPLETED 节点的 task_complete summary（key=task_id, val=output）。
    # dispatch 前由 Orchestrator 填，注入 instruction 让 worker 知道上游做了什么（§6.7）。
    upstream_summaries: dict[str, str] | None = None
    aborted: bool = False  # 被用户中断过（强制 park）；区别于自然 not_done park，供 UI/复盘用


@dataclass
class TaskGraph:
    """校验通过后的可执行 DAG。"""

    nodes: dict[str, TaskNode]

    def deps_of(self, task_id: str) -> list[str]:
        return self.nodes[task_id].task.depends_on


def build_graph(tasks: list[TaskDef], available_workers: set[str]) -> TaskGraph:
    """校验 tasks，通过则编译为 TaskGraph，否则抛 DagValidationError。"""
    _validate(tasks, available_workers)
    return TaskGraph(nodes={t.id: TaskNode(task=t) for t in tasks})


def _validate(tasks: list[TaskDef], available_workers: set[str]) -> None:
    ids = [t.id for t in tasks]
    id_set = set(ids)
    if len(ids) != len(id_set):
        dupes = {tid for tid in ids if ids.count(tid) > 1}
        raise DagValidationError(f"重复 task id: {sorted(dupes)}")

    for t in tasks:
        for dep in t.depends_on:
            if dep not in id_set:
                raise DagValidationError(f"任务 {t.id} 悬空依赖: {dep} 不存在")
        if t.suggested_worker not in available_workers:
            raise DagValidationError(f"任务 {t.id} 未知 worker: {t.suggested_worker}")
        if not t.acceptance and not t.no_verify:
            raise DagValidationError(
                f"任务 {t.id} 无 acceptance 且未标 no_verify——禁止静默通过"
            )

    cycle = _find_cycle(tasks)
    if cycle is not None:
        raise DagValidationError(f"检测到循环依赖: {' → '.join(cycle)}")


def _find_cycle(tasks: list[TaskDef]) -> list[str] | None:
    """DFS 环检测，返回环路径（用于报错），无环返回 None。"""
    graph = {t.id: t.depends_on for t in tasks}
    state: dict[str, int] = {tid: _UNVISITED for tid in graph}
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        state[node] = _IN_STACK
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in state:
                continue  # 悬空依赖已在 _validate 拦截，这里防御
            if state[dep] == _IN_STACK:
                return path[path.index(dep):] + [dep]
            if state[dep] == _UNVISITED:
                found = dfs(dep)
                if found is not None:
                    return found
        state[node] = _DONE
        path.pop()
        return None

    for tid in graph:
        if state[tid] == _UNVISITED:
            found = dfs(tid)
            if found is not None:
                return found
    return None
