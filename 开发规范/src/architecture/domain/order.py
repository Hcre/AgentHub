"""领域层 — 订单实体和领域服务。

规则：不依赖任何框架（FastAPI/Django/SQLAlchemy）。
只能导入标准库和同层的领域接口。
"""
from dataclasses import dataclass
from enum import Enum


class OrderStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """订单实体 — 领域层的核心对象。"""
    order_id: str
    user_id: str
    product_id: str
    quantity: int
    unit_price: float
    discount: float = 0.0  # 折扣金额（由应用层根据 DiscountCalculator 结果写入）
    status: OrderStatus = OrderStatus.PENDING

    @property
    def total(self) -> float:
        """原价总额（未折扣）。"""
        return self.quantity * self.unit_price

    @property
    def final_total(self) -> float:
        """折后应付金额。"""
        return round(self.total - self.discount, 2)
