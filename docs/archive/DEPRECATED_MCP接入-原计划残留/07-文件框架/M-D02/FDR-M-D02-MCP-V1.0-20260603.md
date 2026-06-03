# 框架决策记录 FDR-M-D02-MCP-V1.0-20260603

> 模块 M-D02；本轮新增 3 项 FDR

---

## FDR-D02-001 独立 tracing.py 文件

```
[决策编号] FDR-D02-001
[决策标题] 增加 tracing.py 独立文件（FS-020 未单列）
[决策状态] 已接受
[决策内容] 在 src/agenthub/data/ts_log/ 下新增 tracing.py，提供 trace_id 上下文变量与 get_current_trace_id()。
[决策理由]
  1. MD-MCP M-D02 子模块拆分明确列出 tracing/，FS-020 仅简列 metrics.py + log_config.py
  2. trace_id 上下文注入是 structlog processor 的常见上游依赖，独立文件利于测试
  3. 横切关注点，独立文件避免 log_config.py 臃肿
[拒绝的替代方案]
  方案A: 将 tracing 合并到 log_config.py → 拒绝理由：违反单一职责，log_config.py 已含配置类与工厂
  方案B: 放入 agenthub/core/ → 拒绝理由：core 是横切基础设施，tracing 是 ts_log 子能力
[影响范围] src/agenthub/data/ts_log/tracing.py；测试 test_tracing.py（次轮）
[相关FDR] 无
[来源标注] [DD-M推断:MD-MCP M-D02 tracing 子模块]
```

## FDR-D02-002 主方案 vs 备选方案对比

```
[决策编号] FDR-D02-002
[决策标题] 选用「MetricsRegistry 类 + 模块级工厂」双形态
[决策状态] 已接受
[决策内容] 同时提供 MetricsRegistry 类（带 Settings 注入的强类型方案）与 get_counter / get_gauge / get_histogram 模块级工厂（MD-MCP 函数签名要求）。
[决策理由] 既满足 MD-MCP M-D02 函数签名（`def get_counter(name, labels) -> Counter`），又支持高级场景（自定义 registry / 多 registry 隔离）。
[拒绝的替代方案]
  备选方案A: 仅模块级函数（扁平）
    评估: 文件结构 8 / 注释完整 9 / 接口契约 8 / 代码风格 9 / 可追溯 9 / 框架可追溯 8 = 51
  备选方案B: 仅 MetricsRegistry 类（无模块函数）
    评估: 文件结构 7 / 注释完整 8 / 接口契约 7 / 代码风格 8 / 可追溯 8 / 框架可追溯 7 = 45
  主方案C: 类 + 模块函数双形态
    评估: 文件结构 9 / 注释完整 9 / 接口契约 9 / 代码风格 9 / 可追溯 9 / 框架可追溯 9 = 54
  选择: 主方案 C（总分 54 > 备选 A 51 > 备选 B 45；差距 ≥ 5 不触发平局）
[影响范围] metrics.py；测试 test_metrics.py
[相关FDR] FDR-D02-001
[来源标注] [DD-M推断:多方案对比 4.11 维度]
```

## FDR-D02-003 测试文件组织

```
[决策编号] FDR-D02-003
[决策标题] 测试文件按"被测对象"拆分（test_metrics / test_log_config）
[决策状态] 已接受
[决策内容] 每个生产文件一个测试文件；测试包使用 tests/__init__.py；test 命名 test_{file}_when_{scenario}_then_{expected}。
[决策理由] [DD-001:CS-MCP §1.7] 命名规范要求；用例数 12 拆为 8+4 便于并行。
[拒绝的替代方案]
  方案A: 单文件 test_ts_log.py → 拒绝：违反 [CS-MCP §1.7] 单文件 ≤ 20 函数规则
[影响范围] tests/test_metrics.py, tests/test_log_config.py
[来源标注] [DD-001:CS-MCP §1.7]
```
