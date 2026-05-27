"""文档规范 — 公共 API 注释示例。

对应 conventions/06-documentation_文档规范.md §2.4
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderStatus(Enum):
    """订单状态枚举。"""
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"


@dataclass
class Order:
    """订单实体。

    Attributes:
        order_id: 订单唯一标识（UUID）
        user_id: 用户唯一标识
        product_id: 商品 SKU
        quantity: 购买数量，必须 > 0
        unit_price: 商品单价（元）
        status: 订单状态
    """
    order_id: str
    user_id: str
    product_id: str
    quantity: int
    unit_price: float
    status: OrderStatus = OrderStatus.PENDING


def create_order(
    user_id: str,
    product_id: str,
    quantity: int,
    unit_price: float,
    note: Optional[str] = None,
) -> Order:
    """创建订单。

    从下单到持久化的完整流程：
    1. 校验输入参数
    2. 检查库存（通过 InventoryService）
    3. 计算折扣（通过 DiscountCalculator）
    4. 创建 Order 实体
    5. 持久化（通过 OrderRepository）

    Args:
        user_id: 用户唯一标识（UUID 格式）
        product_id: 商品 SKU
        quantity: 购买数量，必须 > 0
        unit_price: 商品单价（元），必须 > 0
        note: 订单备注（可选，最多 200 字）

    Returns:
        创建的订单对象，状态为 OrderStatus.PENDING

    Raises:
        ValueError: quantity <= 0 或 unit_price <= 0
        InsufficientStockError: 商品库存不足
        UserNotFoundError: 用户不存在

    Example:
        >>> order = create_order("user_001", "SKU-123", 2, 99.00)
        >>> order.status
        <OrderStatus.PENDING: 'pending'>
    """
    if quantity <= 0:
        raise ValueError(f"数量必须大于 0，当前: {quantity}")
    if unit_price <= 0:
        raise ValueError(f"单价必须大于 0，当前: {unit_price}")

    # 实际项目中的后续步骤：
    # 1. inventory_service.check_stock(product_id, quantity)
    # 2. discount = discount_calculator.calculate(...)
    # 3. order = Order(...)
    # 4. order_repository.save(order)

    return Order(
        order_id="ord_demo",
        user_id=user_id,
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
    )
