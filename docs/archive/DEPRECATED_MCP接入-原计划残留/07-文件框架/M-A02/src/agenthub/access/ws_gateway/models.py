"""WS Event Gateway 数据模型 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/models.py
[文件职责] DTO 与领域模型：订阅请求、事件包、连接状态枚举
[所属模块] M-A02
[关联设计规范] MD-M-A02（来自 DD-001）
[功能描述]
  功能1: SubscribeRequest - 客户端订阅/退订消息体
  功能2: EventEnvelope - 推送事件统一包（含 trace_id / emitted_at）
  功能3: WSMessage - socketio 内部事件传输对象
  功能4: ConnectionState - 连接状态枚举（驱动状态机）
[输入输出]
  输入: 客户端 WS 帧 / Event Bus payload / Repository 行
  输出: 内部 handler 使用的强类型对象
[依赖关系]
  依赖文件: 无（仅依赖 pydantic 标准库）
  被依赖文件: server.py, handlers/*, bus_listener.py, offline_queue.py
[注意事项]
  注意1: 所有模型继承 pydantic BaseModel，自动校验类型与必填字段
  注意2: EventEnvelope.emitted_at 必为 timezone-aware ISO8601
  注意3: ConnectionState 状态机须严格按 MD-M-A02 §状态机 转换
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-A02 - 初版（仅注释，无业务代码）
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02]
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConnectionState(str, Enum):
    """WS 客户端连接状态（状态机驱动）.

    状态转移（来自 MD-M-A02 §状态机）：
      Disconnected → connect → Connected
      Connected → subscribe → Subscribed → unsubscribe → Connected
      Connected → ping_timeout(30s) → Disconnected
    """

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"


class SubscribeRequest(BaseModel):
    """客户端订阅请求 DTO.

    [类名] SubscribeRequest
    [职责] 解析客户端 subscribe/unsubscribe 消息体
    [关联设计规范] MD-M-A02 / IC-002
    [属性]
      action: str 必填 enum[subscribe|unsubscribe|ping]
      agent_id: UUID 当 action=subscribe 必填
      topics: list[str] 可选（默认 ["mcp.*"]）
    [来源标注] [DD-001:MD-M-A02/IC-002]
    """

    action: str = Field(..., description="enum[subscribe|unsubscribe|ping]")
    agent_id: UUID | None = Field(default=None, description="订阅者 agent_id")
    topics: list[str] = Field(default_factory=lambda: ["mcp.*"], description="topic 列表")

    @field_validator("action")
    @classmethod
    def _validate_action(cls, v: str) -> str:
        """[函数名] _validate_action
        [职责] 校验 action 字段值域
        [前置条件] v 必为字符串
        [后置条件] v ∈ {subscribe, unsubscribe, ping}
        [来源标注] [DD-001:IC-002 入参定义 msg.action]
        """
        allowed = {"subscribe", "unsubscribe", "ping"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}, got {v!r}")
        return v


class EventEnvelope(BaseModel):
    """事件统一推送包.

    [类名] EventEnvelope
    [职责] 内部事件传输对象，包含 trace_id、emitted_at 与负载
    [关联设计规范] MD-M-A02 / IC-002 出参定义
    [属性]
      event_type: str 必填（如 mcp.running）
      payload: dict 必填
      trace_id: str 必填
      emitted_at: datetime 必填 timezone-aware
    [来源标注] [DD-001:IC-002 出参定义]
    """

    event_type: str = Field(..., description="事件类型，如 mcp.running")
    payload: dict[str, Any] = Field(default_factory=dict, description="事件负载")
    trace_id: str = Field(..., description="链路追踪 ID")
    emitted_at: datetime = Field(..., description="事件发出时间，timezone-aware ISO8601")

    @field_validator("emitted_at")
    @classmethod
    def _ensure_tz_aware(cls, v: datetime) -> datetime:
        """[函数名] _ensure_tz_aware
        [职责] 确保 emitted_at 含时区信息
        [前置条件] v 已为 datetime
        [后置条件] v.tzinfo is not None
        [来源标注] [DD-001:IC-002 emitted_at ISO8601 必填]
        """
        if v.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware ISO8601")
        return v


class WSMessage(BaseModel):
    """socketio 内部传输对象.

    [类名] WSMessage
    [职责] 跨 handler 共享的统一 WS 消息结构
    [关联设计规范] MD-M-A02
    [属性]
      sid: str socketio 会话 ID
      data: dict 消息体
    [来源标注] [DD-M推断:统一 handler 间消息传递类型]
    """

    sid: str
    data: dict[str, Any]
