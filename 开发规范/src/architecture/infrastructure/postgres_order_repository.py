"""基础设施层 — PostgreSQL 订单仓储实现。

规则：实现领域层定义的接口，包含数据库操作细节。
表现层/应用层/领域层不直接引用此模块（通过依赖注入使用）。
"""
from dataclasses import dataclass

from ..domain.order import Order
from ..domain.order_repository import OrderRepository


@dataclass
class PostgresOrderRepository(OrderRepository):
    """PostgreSQL 订单仓储 — 实现领域层定义的 OrderRepository 接口。

    为什么放在基础设施层：
    - 包含数据库连接、SQL 语句等实现细节
    - 换数据库（如 MongoDB）时只需新建一个实现类
    - 领域层完全不感知 PostgreSQL 的存在
    """
    db_url: str

    def save(self, order: Order) -> None:
        """保存订单到 PostgreSQL。"""
        # 实际项目中这里用 psycopg2/asyncpg 执行 INSERT
        print(f"[Postgres] INSERT INTO orders VALUES ({order.order_id}, ...)")

    def find_by_id(self, order_id: str) -> Order | None:
        """从 PostgreSQL 查询订单。"""
        # 实际项目：SELECT * FROM orders WHERE id = ?
        print(f"[Postgres] SELECT * FROM orders WHERE id = {order_id}")
        return None
