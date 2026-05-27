"""领域层 — 折扣计算器（核心业务逻辑）。

规则：纯业务逻辑，无副作用、无 I/O、无框架依赖。
"""
from dataclasses import dataclass


@dataclass
class DiscountResult:
    original: float
    discount: float
    final: float
    reason: str


class DiscountCalculator:
    """折扣计算器 — 所有折扣规则集中在此。
    
    为什么放在领域层：
    - 折扣规则是核心业务，不依赖数据库或 HTTP
    - 换框架（FastAPI → Flask）时无需修改
    - 单元测试不需要 Mock 任何依赖
    """

    VIP_DISCOUNT_RATE = 0.8    # VIP 8 折
    BULK_DISCOUNT_RATE = 0.9   # 满 5 件 9 折
    BULK_THRESHOLD = 5

    def calculate(
        self, original: float, quantity: int, is_vip: bool = False
    ) -> DiscountResult:
        """计算折扣后的最终价格。

        Args:
            original: 原价（单件）
            quantity: 购买数量
            is_vip: 是否 VIP 用户

        Returns:
            DiscountResult: 包含原价、折扣金额、最终价格、折扣原因
        """
        total = original * quantity
        discount = 0.0
        reasons = []

        if is_vip:
            discount = total * (1 - self.VIP_DISCOUNT_RATE)
            reasons.append(f"VIP {self.VIP_DISCOUNT_RATE*100:.0f}% 折扣")

        if quantity >= self.BULK_THRESHOLD:
            bulk_discount = total * (1 - self.BULK_DISCOUNT_RATE)
            discount = max(discount, bulk_discount)  # 取最优折扣
            reasons.append(f"满{self.BULK_THRESHOLD}件 {self.BULK_DISCOUNT_RATE*100:.0f}% 折扣")

        if not reasons:
            reasons.append("无折扣")

        final = total - discount
        return DiscountResult(
            original=total,
            discount=round(discount, 2),
            final=round(final, 2),
            reason=" + ".join(reasons),
        )
