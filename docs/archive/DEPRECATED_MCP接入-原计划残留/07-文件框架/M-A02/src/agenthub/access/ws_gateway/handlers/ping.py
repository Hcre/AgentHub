"""ping / pong 心跳处理 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/handlers/ping.py
[文件职责] 心跳与 ping_timeout 状态机驱动
[所属模块] M-A02
[关联设计规范] MD-M-A02 §状态机 Connected → ping_timeout(30s) → Disconnected
[功能描述]
  功能1: on_ping - 响应客户端 ping（更新最后心跳时间）
  功能2: on_pong - 处理 socketio 自动 pong
  功能3: mark_timeout - 检测心跳超 30s 的连接并强制 disconnect
[输入输出]
  输入: 客户端 ping 帧
  输出: pong 帧 + session last_seen 更新
[依赖关系]
  依赖文件: subscription_store（更新 last_seen）
  被依赖文件: server.py
[注意事项]
  注意1: ping_timeout=30s 硬编码于 socketio.AsyncServer 配置，与 MD 一致
  注意2: mark_timeout 周期任务使用 asyncio.create_task
  注意3: 标记超时不立刻 kill，先发一次 ping 探测
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-02
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02 §状态机]
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.access.ws_gateway.subscription_store import SubscriptionStore

log = get_logger(__name__)

PING_TIMEOUT_SEC = 30  # 与 MD-M-A02 状态机一致


def register(sio: Any, store: "SubscriptionStore") -> None:
    """[函数名] register
    [职责] 绑定 ping 事件，启动超时巡检任务
    [来源标注] [DD-001:FS-002 handlers/ping.py]
    """
    ...


async def on_ping(sid: str) -> None:
    """[函数名] on_ping
    [职责] 响应客户端 ping，更新 last_seen
    [参数说明]
      sid: str 必填
    [后置条件] store[sid].last_seen = now
    [并发安全] 安全
    [来源标注] [DD-001:MD-M-A02 状态机]
    """
    ...


async def on_pong(sid: str) -> None:
    """[函数名] on_pong
    [职责] 处理 socketio 自动 pong 帧
    [来源标注] [DD-001:MD-M-A02 状态机]
    """
    ...


async def mark_timeout(sio: Any, store: "SubscriptionStore") -> None:
    """[函数名] mark_timeout
    [职责] 巡检所有 sid，超 30s 无心跳的连接强制 disconnect
    [参数说明]
      sio: socketio.AsyncServer 必填
      store: SubscriptionStore 必填
    [并发安全] 周期任务（建议 5s 巡检）
    [性能约束] 巡检 1k 连接 < 100ms
    [来源标注] [DD-001:MD-M-A02 ping_timeout 30s]
    """
    ...


def start_timeout_loop(sio: Any, store: "SubscriptionStore", interval: int = 5) -> asyncio.Task[None]:
    """[函数名] start_timeout_loop
    [职责] 启动 mark_timeout 周期巡检任务
    [参数说明]
      sio: socketio.AsyncServer
      store: SubscriptionStore
      interval: int 默认 5（秒）
    [来源标注] [DD-M推断:封装为长驻 task]
    """
    ...
