"""事件总线抽象。

架构约束：Task Engine 状态变更通过事件溯源，不直接改状态；
领域事件（上行）经 EventBus 发布 → Redis Pub/Sub → WS 推送（见 infrastructure/ws）。

此处定义进程内 EventBus 协议与一个基础实现；跨进程广播由 Redis 桥接补充。
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.domain.events.base import DomainEvent

logger = logging.getLogger(__name__)

Handler = Callable[[DomainEvent], Awaitable[None]]


class EventBus(Protocol):
    """L3 通过此接口发布领域事件，不感知订阅者实现。"""

    async def publish(self, event: DomainEvent) -> None: ...

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None: ...


class InMemoryEventBus:
    """进程内事件总线。订阅者异常被隔离，不影响其他订阅者与主流程。"""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.debug("event %s 无订阅者", type(event).__name__)
            return
        results = await asyncio.gather(
            *(h(event) for h in handlers), return_exceptions=True
        )
        for r in results:
            if isinstance(r, Exception):
                logger.exception("事件处理失败: %s", r)


_bus: InMemoryEventBus | None = None


def get_event_bus() -> InMemoryEventBus:
    """全局事件总线单例（FastAPI DI 入口）。"""
    global _bus
    if _bus is None:
        _bus = InMemoryEventBus()
    return _bus
