# 文件框架结构 FF-M-D02-MCP-V1.0-20260603

> 模块 M-D02 TS & Log；来源 [DD-001:FS-020 / MD-MCP M-D02 / IC-018]
> 代码风格: [DD-001:CS-MCP §1]（Python 3.11 + Google docstring + mypy strict）
> 多方案对比见 FDR-M-D02 §FDR-002

---

## [模块编号] M-D02
## [模块名称] TS & Log
## [文件框架]

```
src/agenthub/data/ts_log/
├── __init__.py                ← [职责：模块初始化，导出公共接口]
├── metrics.py                 ← [职责：Prometheus Registry + 三类指标工厂]
│   - [类: MetricsRegistry - 集中注册 Counter/Gauge/Histogram]
│   - [函数: get_counter / get_gauge / get_histogram - 模块级工厂]
├── log_config.py              ← [职责：structlog 配置 + JSON Lines 输出]
│   - [类: LogConfig - 配置数据类]
│   - [函数: configure_logging - 启动时初始化]
│   - [函数: get_logger - 工厂方法]
├── tracing.py                 ← [职责：trace_id 上下文注入（[DD-M推断]）]
│   - [函数: get_current_trace_id / bind_trace_id]
└── tests/                     ← [职责：单元测试]
    ├── __init__.py
    ├── test_metrics.py        ← [职责：MetricsRegistry 行为验证；用例 8+]
    │   - [测试场景1: counter 正常创建]
    │   - [测试场景2: counter 幂等性]
    │   - [测试场景3: gauge set/get]
    │   - [测试场景4: histogram observe]
    │   - [测试场景5: render 边界]
    │   - [测试场景6: 模块级工厂]
    │   - [测试场景7: 高基数 label 静态提示]
    │   - [测试场景8: 1000 指标 < 100ms 性能]
    └── test_log_config.py     ← [职责：LogConfig 初始化；用例 4+]
        - [测试场景1: 默认值]
        - [测试场景2: configure_logging 不抛]
        - [测试场景3: get_logger 绑定]
        - [测试场景4: JSON Lines 输出]
```

## [文件间依赖关系]

```
__init__.py  →  metrics.py / log_config.py
metrics.py   →  agenthub.core.config（仅类型，TYPE_CHECKING）
log_config.py → agenthub.core.config
tracing.py   →  （仅 contextvars + structlog；无业务依赖）
tests/       →  metrics.py / log_config.py
```

无循环依赖。无跨模块文件引用。

## [合规检查清单]（soul 4.7）

| 检查项 | 检查标准 | 通过情况 |
|--------|---------|---------|
| 目录层级 | 3 层（data/ts_log/tests） | ✓ |
| 文件命名 | snake_case | ✓ |
| 文件职责 | 单一职责（metrics / log / trace / tests） | ✓ |
| 依赖关系 | 无循环；TYPE_CHECKING 隔离 | ✓ |
| 最佳实践 | __init__.py 显式 __all__；测试包独立 | ✓ |

合规度: 高（5/5 通过）

## [来源标注] [DD-001:FS-020 / MD-MCP M-D02]
