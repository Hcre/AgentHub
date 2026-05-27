"""单元测试 — 折扣计算。

运行: pytest test_discount.py -v

覆盖场景：
- 正常路径 (Happy Path)
- 边界条件（零值、极大值）
- 异常路径（非法输入）
- 命名规范：test_方法_场景_期望
"""
import pytest
from discount import calculate_discount, split_bill


# === calculate_discount 测试 ===

class TestCalculateDiscount:
    """折扣计算测试集。每个测试方法只验证一个场景。"""

    # --- Happy Path ---
    def test_calculate_discount_normal_user_no_discount(self):
        """普通用户，不满足任何折扣条件。"""
        result = calculate_discount(total=100.0, is_vip=False, quantity=1)
        assert result == 100.0

    def test_calculate_discount_vip_gets_20_percent_off(self):
        """VIP 用户享受 8 折。"""
        result = calculate_discount(total=100.0, is_vip=True, quantity=1)
        assert result == 80.0

    def test_calculate_discount_bulk_5_items_gets_10_percent_off(self):
        """买 5 件享受 9 折。"""
        result = calculate_discount(total=100.0, is_vip=False, quantity=5)
        assert result == 90.0

    def test_calculate_discount_vip_bulk_gets_best_discount(self):
        """VIP 且买 5 件，取最优折扣（VIP 8 折 > 满减 9 折）。"""
        result = calculate_discount(total=100.0, is_vip=True, quantity=5)
        assert result == 80.0  # 取 VIP 折扣，而非满减

    # --- 边界条件 ---
    def test_calculate_discount_minimal_amount(self):
        """极小金额。"""
        result = calculate_discount(total=0.01, is_vip=True, quantity=1)
        assert result == 0.01  # 四舍五入后可能还是 0.01

    # --- 异常路径 ---
    def test_calculate_discount_zero_amount_raises_error(self):
        """金额为 0 应抛异常。"""
        with pytest.raises(ValueError, match="金额必须大于 0"):
            calculate_discount(total=0.0)

    def test_calculate_discount_negative_amount_raises_error(self):
        """金额为负数应抛异常。"""
        with pytest.raises(ValueError, match="金额必须大于 0"):
            calculate_discount(total=-10.0)

    def test_calculate_discount_zero_quantity_raises_error(self):
        """数量为 0 应抛异常。"""
        with pytest.raises(ValueError, match="数量必须大于 0"):
            calculate_discount(total=100.0, quantity=0)


# === split_bill 测试 ===

class TestSplitBill:
    """分账测试 — 演示边界和精度处理。"""

    def test_split_bill_even_division(self):
        """整数均分。"""
        result = split_bill(total=100.0, num_people=2)
        assert result == 50.0

    def test_split_bill_round_up_to_cent(self):
        """不能整除时向上取整到分。"""
        result = split_bill(total=100.0, num_people=3)
        # 100/3 = 33.333... → 向上取整到 33.34
        assert result == 33.34

    def test_split_bill_single_person(self):
        """一个人付全部。"""
        result = split_bill(total=99.99, num_people=1)
        assert result == 99.99

    def test_split_bill_zero_people_raises_error(self):
        """人数为 0 应抛异常。"""
        with pytest.raises(ValueError, match="人数必须大于 0"):
            split_bill(total=100.0, num_people=0)

    def test_split_bill_negative_amount_raises_error(self):
        """金额为负应抛异常。"""
        with pytest.raises(ValueError, match="金额必须大于 0"):
            split_bill(total=-50.0, num_people=2)
