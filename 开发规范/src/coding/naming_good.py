"""命名规范 — 正例。

对比 naming_bad.py 查看反模式。
"""

from dataclasses import dataclass


# ✅ 见名知意
def calculate_total_price(item_prices: list[float]) -> float:
    """计算商品总价。"""
    return sum(item_prices)


def calculate_user_score(user_activity: float, base_weight: float) -> float:
    """计算用户活跃度得分，基重为百分比。"""
    return user_activity * base_weight / 100


# ✅ 用常量代替魔法数字
LEGAL_ADULT_AGE = 18  # 法定成年年龄


def is_legal_adult(age: int) -> bool:
    """判断是否达到法定成年年龄。"""
    return age >= LEGAL_ADULT_AGE


# ✅ 布尔变量用 is/has/can 前缀
is_active = True
has_permission = False
can_edit = True


# ✅ 统一 snake_case 风格
user_name = "张三"
user_age = 28
user_address = "北京"


@dataclass
class UserProfile:  # ✅ PascalCase 类名
    """用户资料。"""
    display_name: str
    email: str
    is_verified: bool = False


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger(__name__)
    log.info("总价: %s", calculate_total_price([10.0, 20.0, 30.0]))
    log.info("成年: %s", is_legal_adult(20))
    log.info("未成年: %s", is_legal_adult(15))
