"""WS Event Gateway 模块 (M-A02).

本模块为 AgentHub 系统的 WebSocket 事件推送层，负责：
  1. 维护客户端长连接（python-socketio + AsyncServer）
  2. 管理 topic 订阅关系（PG DE-013 + Redis hash）
  3. 离线事件缓冲（Redis Stream 兜底）
  4. 将 Event Bus 事件（来自 M-EV01）按订阅关系转推 WS 客户端

设计模式：Observer + Adapter
  - Observer：BusListener 监听 Event Bus，触发对已订阅客户端的推送
  - Adapter：handlers/* 将 socketio 协议适配为内部领域事件

关联设计规范：FS-002 / MD-M-A02 / IC-002（来自 DD-001）
关联代码风格：CS-MCP §1 Python 风格指南

[DD-001:FS-002/MD-M-A02/IC-002]
[创建日期] 2026-06-02
[作者] DD-M-A02
"""

from __future__ import annotations

from agenthub.access.ws_gateway.bus_listener import BusListener
from agenthub.access.ws_gateway.exceptions import (
    ACLError,
    AuthError,
    PushFailedError,
    RedisConnectionError,
)
from agenthub.access.ws_gateway.models import (
    ConnectionState,
    EventEnvelope,
    SubscribeRequest,
    WSMessage,
)
from agenthub.access.ws_gateway.offline_queue import OfflineQueue
from agenthub.access.ws_gateway.server import WSServer
from agenthub.access.ws_gateway.subscription_store import SubscriptionStore

__all__ = [
    "WSServer",
    "SubscriptionStore",
    "OfflineQueue",
    "BusListener",
    "AuthError",
    "ACLError",
    "RedisConnectionError",
    "PushFailedError",
    "SubscribeRequest",
    "EventEnvelope",
    "WSMessage",
    "ConnectionState",
]
