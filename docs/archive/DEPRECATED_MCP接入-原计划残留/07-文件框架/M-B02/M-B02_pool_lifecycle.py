"""M-B02 ProcessStateMachine 状态机（State Machine 模式）.

[文件路径] src/agenthub/application/pool/lifecycle.py
[文件职责] 管理进程状态机转换（5 业务状态 + 2 异常状态）
[所属模块] M-B02
[关联设计规范] MD-MCP-V1.0-20260602
[设计模式] State Machine
[功能描述]
  功能1: 状态机转换（idle ↔ spawn_requested ↔ spawning ↔ running ↔ recycling ↔ recycled）
  功能2: 异常路径（health_fail × 3 → zombie → recycled）
  功能3: 重试路径（spawning → spawn_fail → reserved_slot → retry → spawning max 3）
  功能4: 转换日志 + EventBus 发布
[输入输出]
  输入: Process 实体 + 事件
  输出: 更新 state 后的 Process 实体
[依赖关系]
  依赖文件: agenthub.application.pool.models
  被依赖文件: agenthub.application.pool.pool, agenthub.application.pool.spawner
[注意事项]
  注意1: 状态转换必须经过 transition() 统一入口（禁止直接修改 state 字段）
  注意2: zombie 状态必须等待 recycle 后才转 recycled
  注意3: spawn_fail 重试上限 3 次（DD-001 MD-MCP-M-B02 约束）
  注意4: 状态转换必须 publish event（topic: process.{new_state}）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.6 异常处理 + 状态机必须事件驱动
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:MD-MCP-M-B02]
"""
from __future__ import annotations

from agenthub.application.pool.models import Process, ProcessState
from agenthub.core.logging import get_logger

log = get_logger(__name__)


# 状态转换表（DD-001 MD-MCP-M-B02 严格定义）
TRANSITIONS: dict[ProcessState, dict[str, ProcessState]] = {
    ProcessState.IDLE: {
        "spawn_requested": ProcessState.SPAWN_REQUESTED,
    },
    ProcessState.SPAWN_REQUESTED: {
        "spawn_start": ProcessState.SPAWNING,
    },
    ProcessState.SPAWNING: {
        "spawn_ok": ProcessState.RUNNING,
        "spawn_fail": ProcessState.SPAWN_REQUESTED,  # 重试
    },
    ProcessState.RUNNING: {
        "idle_5min": ProcessState.IDLE,
        "health_fail": ProcessState.RUNNING,  # fail_count++
        "recycle_request": ProcessState.RECYCLING,
    },
    ProcessState.RECYCLING: {
        "recycle_ok": ProcessState.RECYCLED,
    },
    ProcessState.RECYCLED: {},  # 终态
    ProcessState.ZOMBIE: {
        "recycle_request": ProcessState.RECYCLING,
    },
}


class ProcessStateMachine:
    """进程状态机（State Machine 模式）.

    Attributes:
        process: 关联的 Process 实体
        transitions: 状态转换表（与 TRANSITIONS 同步）
    """

    def __init__(self, process: Process) -> None:
        """初始化状态机.

        Args:
            process: 关联进程
        """
        self.process: Process = process
        self.transitions: dict[ProcessState, dict[str, ProcessState]] = TRANSITIONS

    def transition(self, event: str) -> Process:
        """触发状态转换.

        Args:
            event: 事件名（如 "spawn_requested" / "spawn_ok" / "health_fail"）

        Returns:
            更新后的 Process 实体

        Raises:
            ValueError: 当前状态不支持该事件

        前置条件: 事件在 transitions[state] 中存在
        后置条件: process.state 已更新；日志记录；EventBus 发布
        并发安全: 单进程内串行（per-process lock）
        幂等性: 是（同一事件重复触发产生相同新状态）
        """
        # 1. 查询 transitions[self.process.state][event]
        # 2. 不存在 → raise ValueError
        # 3. 存在 → self.process.state = new_state
        # 4. health_fail 特殊：self.process.fail_count++
        # 5. fail_count == 3 → transition(zombie)
        # 6. log.info + EventBus publish
        raise NotImplementedError("DD-M 仅产出框架，业务代码由开发工程师实现")
