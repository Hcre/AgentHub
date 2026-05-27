"""被测代码 — 折扣计算（纯业务逻辑，无外部依赖）。

这样设计的好处：
- 单元测试不需要 Mock 任何东西
- 换数据库/框架时这段代码不用改
"""

import math


def calculate_discount(total: float, is_vip: bool = False, quantity: int = 1) -> float:
    """计算折扣后的最终价格。

    Args:
        total: 原价总金额
        is_vip: 是否 VIP 用户
        quantity: 购买数量

    Returns:
        折扣后价格（保留 2 位小数）

    Raises:
        ValueError: total 为负数或零
        ValueError: quantity 为负数或零
    """
    if total <= 0:
        raise ValueError(f"金额必须大于 0，当前: {total}")
    if quantity <= 0:
        raise ValueError(f"数量必须大于 0，当前: {quantity}")

    discount = 0.0

    if is_vip:
        discount = max(discount, total * 0.2)  # VIP 8 折

    if quantity >= 5:
        discount = max(discount, total * 0.1)  # 满 5 件 9 折

    return round(total - discount, 2)


def split_bill(total: float, num_people: int) -> float:
    """AA 制分账，每人应付金额（向上取整到分）。

    Args:
        total: 总金额
        num_people: 人数

    Returns:
        每人应付金额

    Raises:
        ValueError: total 为负数或零
        ValueError: num_people 为负数或零
    """
    if total <= 0:
        raise ValueError(f"金额必须大于 0，当前: {total}")
    if num_people <= 0:
        raise ValueError(f"人数必须大于 0，当前: {num_people}")

    # 向上取整到分（0.01）
    per_person = total / num_people
    return math.ceil(per_person * 100) / 100
