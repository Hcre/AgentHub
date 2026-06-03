"""M-B02 Process Pool Manager 数据模型定义.

[文件路径] src/agenthub/application/pool/models.py
[文件职责] 定义 ProcessPool 模块的核心数据模型（Process / ProcessState 枚举 / LRU 节点）
[所属模块] M-B02
[关联设计规范] MD-MCP-V1.0-20260602 / IC-004
[功能描述]
  功能1: 定义 Process 实体（pid / mcp_id / ws_id / state / created_at / last_used_at）
  功能2: 定义 ProcessState 枚举（idle / spawn_requested / spawning / running / recycling / recycled / zombie）
  功能3: 定义 LRU 节点（双链表 + dict 实现 LRU 驱逐）
  功能4: 定义 PoolStats 统计（active_count / idle_count / zombie_count）
[输入输出]
  输入: 模型构造参数
  输出: 不可变 / 可变数据类（pydantic BaseModel）
[依赖关系]
  依赖文件: pydantic, uuid, datetime
  被依赖文件: agenthub.application.pool.pool, agenthub.application.pool.spawner, agenthub.application.pool.lifecycle
[注意事项]
  注意1: Process 必须为可变对象（状态机转换时更新 state 字段）
  注意2: ProcessState 枚举值与状态机 transition 事件严格对应（见 lifecycle.py）
  注意3: LRU 节点 O(1) 增删（dict + 双向链表）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.3 类型注解 + §1.4 注释规范
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:MD-MCP-M-B02 + IC-004 + DD洞察-1]
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProcessState(str, Enum):
    """进程状态机枚举（5 业务状态 + 2 异常状态）.

    转换规则:
      idle → spawn_requested → spawning → running → idle (5min idle) → recycling → recycled
      running → health_fail × 3 → zombie → recycled
      spawning → spawn_fail → reserved_slot → retry → spawning（max 3）
    """

    IDLE = "idle"
    SPAWN_REQUESTED = "spawn_requested"
    SPAWNING = "spawning"
    RUNNING = "running"
    RECYCLING = "recycling"
    RECYCLED = "recycled"
    ZOMBIE = "zombie"  # 健康检查失败 3 次


class Process(BaseModel):
    """进程实体.

    Attributes:
        pid: 操作系统进程 ID
        mcp_id: 关联的 MCP UUID
        ws_id: 所属 workspace UUID
        state: 当前状态
        created_at: 创建时间
        last_used_at: 最近一次使用时间（idle 计算依据）
        fail_count: 健康检查连续失败次数
        trace_id: 关联 trace_id（用于审计）
    """

    pid: int = Field(..., ge=1)
    mcp_id: UUID
    ws_id: UUID
    state: ProcessState = ProcessState.IDLE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime = Field(default_factory=datetime.utcnow)
    fail_count: int = Field(default=0, ge=0, le=10)
    trace_id: str


class LRUNode(BaseModel):
    """LRU 双向链表节点.

    Attributes:
        process: 关联的进程
        prev: 前驱节点 ID
        next: 后继节点 ID
    """

    process: Process
    prev: Optional[str] = None
    next: Optional[str] = None


class PoolStats(BaseModel):
    """进程池统计.

    Attributes:
        ws_id: workspace UUID
        active_count: 运行中进程数
        idle_count: 空闲进程数
        zombie_count: 僵尸进程数
        max_capacity: 64 / ws
    """

    ws_id: UUID
    active_count: int = 0
    idle_count: int = 0
    zombie_count: int = 0
    max_capacity: int = 64
