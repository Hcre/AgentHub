"""领域层 — 订单仓储接口（抽象）。

规则：只定义接口，不实现细节。
具体实现（如 PostgresOrderRepository）放在 infrastructure/ 中。
"""
from abc import ABC, abstractmethod

from .order import Order


class OrderRepository(ABC):
    """订单仓储接口 — 领域层只依赖这个抽象。

    为什么用抽象接口：
    - 应用层/领域层不需要知道数据存在 MySQL 还是 MongoDB
    - 换数据库时只改 infrastructure/ 中的实现
    - 单元测试用 MemoryOrderRepository 替代真实数据库
    """

    @abstractmethod
    def save(self, order: Order) -> None:
        """保存订单。"""
        ...

    @abstractmethod
    def find_by_id(self, order_id: str) -> Order | None:
        """根据 ID 查找订单。"""
        ...
