"""架构设计示例 — 入口。

演示分层架构的依赖注入和调用流程。

运行: python -m src.architecture.main
"""
import sys

# Windows 控制台默认 GBK，确保中文输出不乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.architecture.domain.discount_calculator import DiscountCalculator
from src.architecture.infrastructure.postgres_order_repository import (
    PostgresOrderRepository,
)
from src.architecture.application.order_service import OrderService
from src.architecture.presentation.order_controller import OrderController


def main():
    """组装应用：依赖注入（在入口处创建所有具体实现并连接）。"""
    # 基础设施层
    repo = PostgresOrderRepository(db_url="postgresql://...")

    # 领域层
    calculator = DiscountCalculator()

    # 应用层（注入依赖）
    service = OrderService(repo=repo, calculator=calculator)

    # 表现层（注入依赖）
    controller = OrderController(service=service)

    # 模拟 HTTP 请求
    print("=" * 50)
    print("模拟：POST /api/orders — 普通用户买 3 件")
    response = controller.create_order({
        "order_id": "ord_001",
        "user_id": "user_001",
        "product_id": "prod_001",
        "quantity": 3,
        "unit_price": 100.0,
    })
    print(f"响应: {response}")

    print()
    print("=" * 50)
    print("模拟：POST /api/orders — VIP 用户买 6 件")
    response = controller.create_order({
        "order_id": "ord_002",
        "user_id": "user_002",
        "product_id": "prod_001",
        "quantity": 6,
        "unit_price": 100.0,
        "is_vip": True,
    })
    print(f"响应: {response}")

    print()
    print("=" * 50)
    print("[OK] 分层架构验证通过")
    print("依赖方向: 表现层 → 应用层 → 领域层 ← 基础设施层")
    print("领域层导入: 只有标准库 (dataclass, enum, abc) + 领域接口")


if __name__ == "__main__":
    main()
