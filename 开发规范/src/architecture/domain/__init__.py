"""领域层 — 模块入口。"""
from .order import Order, OrderStatus
from .order_repository import OrderRepository
from .discount_calculator import DiscountCalculator, DiscountResult

__all__ = [
    "Order",
    "OrderStatus",
    "OrderRepository",
    "DiscountCalculator",
    "DiscountResult",
]
