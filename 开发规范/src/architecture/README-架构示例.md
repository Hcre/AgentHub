# 架构设计示例 — 分层架构

> **👤 人类参考** | 对应规范：`conventions/01-architecture_架构设计规范.md`
> 技术栈：Python 3.12+ | 运行：`python main.py`

## 目录结构

```
architecture/
├── main.py              # 入口 + 依赖注入
├── presentation/        # 表现层 — HTTP 控制器
│   ├── __init__.py
│   └── order_controller.py
├── application/         # 应用层 — 业务编排
│   ├── __init__.py
│   └── order_service.py
├── domain/              # 领域层 — 核心业务（不依赖任何框架）
│   ├── __init__.py
│   ├── order.py
│   ├── order_repository.py       # 接口定义
│   └── discount_calculator.py
└── infrastructure/      # 基础设施层 — 数据库实现
    ├── __init__.py
    └── postgres_order_repository.py
```

## 分层规则

- **表现层** → 应用层 → 领域层：单向依赖
- **领域层** 不 import 任何框架（FastAPI/Django/Flask/ORM）
- **基础设施层** 实现领域层定义的接口
- **跨层调用**（表现层直接调基础设施层）：禁止

## 自动校验（红线落地）

`importlinter.ini` 把上述分层规则写成可校验契约（对应规范 §二）：

```bash
pip install import-linter
lint-imports --config src/architecture/importlinter.ini
```
