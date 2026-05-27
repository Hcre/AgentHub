"""应用层 — 订单服务（业务编排）。

规则：编排领域对象，不包含业务规则本身。
业务规则在 domain/ 中，应用层只负责"先做什么、后做什么"。
"""
import logging

from ..domain.order import Order
from ..domain.order_repository import OrderRepository
from ..domain.discount_calculator import DiscountCalculator

logger = logging.getLogger(__name__)


class OrderService:
    """订单服务 — 应用层业务编排。

    职责：
    - 编排创建订单的流程（计算折扣 → 创建实体 → 保存）
    - 事务管理（实际项目中用 Unit of Work 模式）
    - 不包含折扣计算逻辑（委托给 DiscountCalculator）
    """

    def __init__(self, repo: OrderRepository, calculator: DiscountCalculator):
        # 依赖注入：应用层不创建具体实现，由外部传入
        self.repo = repo
        self.calculator = calculator

    def place_order(
        self,
        order_id: str,
        user_id: str,
        product_id: str,
        quantity: int,
        unit_price: float,
        is_vip: bool = False,
    ) -> Order:
        """下单流程：计算折扣 → 创建订单 → 持久化。

        Args:
            order_id: 订单 ID
            user_id: 用户 ID
            product_id: 商品 ID
            quantity: 数量
            unit_price: 单价
            is_vip: 是否 VIP

        Returns:
            创建的订单对象
        """
        # 1. 领域层：计算折扣
        discount_result = self.calculator.calculate(
            original=unit_price,
            quantity=quantity,
            is_vip=is_vip,
        )
        logger.info("折扣计算完成 | reason=%s | final=%.2f", discount_result.reason, discount_result.final)

        # 2. 领域层：创建订单实体（把折扣写入订单，否则折扣计算白做了）
        order = Order(
            order_id=order_id,
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            discount=discount_result.discount,
        )

        # 3. 基础设施层：持久化
        self.repo.save(order)

        return order
