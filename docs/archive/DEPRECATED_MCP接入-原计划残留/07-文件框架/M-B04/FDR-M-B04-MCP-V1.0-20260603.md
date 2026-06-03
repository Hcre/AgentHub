# 框架决策记录 FDR-M-B04-MCP-V1.0-20260603

> 模块 M-B04 Approval Engine 重大框架决策
> 作者 DD-M-B04-20260603

---

## FDR-B04-001 拆分 scanner.py 独立文件

- [决策状态] 已接受
- [决策内容] 将 `timeout_scan` 从 services.py 中拆出为独立 `scanner.py`，作为 arq 任务入口
- [决策理由] (1) SRP：HTTP 入口的 services 与 worker 入口职责不同；(2) arq 任务注册需要顶层 callable，独立文件便于 worker 配置；(3) Leader Election 协调逻辑可隔离测试
- [拒绝的替代方案] 方案 B：保留在 services.py 内仅暴露函数 — 拒绝理由：与 worker 注册耦合，单测需引入 arq stub
- [影响范围] services.py / scanner.py / arq worker 配置
- [来源标注] [DD-M-B04 推断: MD:M-B04 提及 timeout_scan 但未拆文件]

---

## FDR-B04-002 schemas.py 独立 DTO 集合

- [决策状态] 已接受
- [决策内容] 新建 schemas.py 集中放置 CheckRequest / DecideRequest / Decision enum / ApprovalEvent
- [决策理由] FS-008 未列出但 IC-005/006 入出参字段多；集中可被 tests / scanner / events 复用，且符合 FastAPI 推荐 schemas 子模块惯例（M-B01 同样有 schemas.py）
- [拒绝的替代方案] 方案 B：散落在 controllers.py 内联定义 — 拒绝：tests 与 scanner 复用困难
- [影响范围] controllers / services / scanner / tests
- [来源标注] [DD-M-B04 推断 + 参考 FS-005 M-B01 schemas.py]

---

## FDR-B04-003 exceptions.py 独立异常集合

- [决策状态] 已接受
- [决策内容] 新建 exceptions.py，所有 ApprovalError 子类集中定义
- [决策理由] CS §1.6 要求自定义异常基类；集中定义便于 controllers 统一映射 HTTP 错误码、便于 tests import
- [拒绝的替代方案] 散落在各自抛出文件 — 拒绝：循环依赖风险、错误码表难统一维护
- [影响范围] 全模块
- [来源标注] [DD-001:CS §1.6 + IC-005/006 错误码]

---

## FDR-B04-004 DecideResponse 增加 duplicate / original_decision_id 字段

- [决策状态] 已接受
- [决策内容] DecideResponse 新增 `duplicate: bool = False` 与 `original_decision_id: UUID|None`，配合 409 APPROVAL_DUPLICATE 错误码
- [决策理由] IC-006 要求"幂等返回上次结果"但只规定 409；客户端难区分"失败"与"幂等命中"。明示字段可让客户端正常处理
- [拒绝的替代方案] 仅 HTTP 200 返回 — 拒绝：违反 IC-006 错误码表
- [影响范围] schemas.py / controllers.py
- [来源标注] [DD-M-B04 推断 + IC-006 错误码]

---

## FDR-B04-005 CheckResponse 增加 fail_safe 字段

- [决策状态] 已接受
- [决策内容] CheckResponse 增加 `fail_safe: bool = False`，标识"DB 不可达时的保守 pending"
- [决策理由] services 层 fail-safe 决策需要可观察性；监控可统计 fail_safe=True 比例触发告警
- [拒绝的替代方案] 仅日志告警 — 拒绝：上游/客户端无法感知降级
- [影响范围] schemas.py / services.py / controllers.py
- [来源标注] [DD-M-B04 推断 + IC-005 fail-safe 语义]

---

## FDR-B04-006 build_key 静态方法集中复合键算法

- [决策状态] 已接受
- [决策内容] AllowlistCache.build_key(ws, mcp, tool, args_hash) 集中 30d allowlist 复合键算法
- [决策理由] 避免 services.check_and_queue 与 services.decide 各自重复拼接，与 ArgsHasher 一致原则
- [拒绝的替代方案] services 内联 — 拒绝：DRY 违反
- [影响范围] allowlist.py / services.py
- [来源标注] [DD-M-B04 推断 + ADR-006 单一来源原则延伸]

---

## FDR-B04-007 主方案 vs 备选方案对比（合规 R20）

### 主方案 A：services.py 单文件编排 + 拆分 scanner/schemas/exceptions

### 备选方案 B：services.py 拆为 check_service / decide_service / scan_service 三文件

| 维度 (权重) | A 得分 | B 得分 |
|----|----|----|
| 文件结构合规度 (0.22) | 9 (与 FS-008 对齐) | 7 (新增子拆分偏离 FS) |
| 注释完整度 (0.22) | 9 | 8 (注释分散) |
| 接口契约注释化完整度 (0.18) | 9 | 9 |
| 代码风格合规度 (0.13) | 9 | 8 |
| 设计可追溯性 (0.13) | 9 | 7 (拆分超出 MD 模式约束) |
| 文件框架可追溯性 (0.12) | 9 | 8 |

**A 总分** = 9×0.22 + 9×0.22 + 9×0.18 + 9×0.13 + 9×0.13 + 9×0.12 = **9.00**
**B 总分** = 7×0.22 + 8×0.22 + 9×0.18 + 8×0.13 + 7×0.13 + 8×0.12 = **7.69**

差距 = **1.31** (＞0 但 ＜5)，按选择规则采用 A，并标注：方案 B 更适合"未来 check_service 与 decide_service 演化为独立微服务"的场景，已记入演进事项。

[来源标注] [DD-M-B04 推断 + soul 4.11]
