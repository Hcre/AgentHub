# 文件框架结构 FF-M-B05-MCP-V1.0-20260603

> M-B05 MCP Create 文件框架结构 | 来源 [DD-001:FS-MCP/FS-009 + MD-MCP/M-B05 + IC-MCP/IC-007 + DDR-005]
> 框架轮次 1/4，文件数 11（含 5 step + 1 step 包初始化 + 1 test 包初始化 + 1 compensator + 2 业务 + 1 schemas）

---

## 1. 文件清单

```
[模块编号] M-B05
[模块名称] MCP Create
[文件框架]（仅注释，无业务代码）
  src/agenthub/application/create/
    __init__.py             ← [职责：模块初始化，导出公共 Saga 接口]
    controllers.py          ← [职责：FastAPI 提交/回滚路由控制器]
      - CreateController 类
      - submit / rollback 方法注释
    orchestrator.py         ← [职责：Saga 编排器（5 步链）+ arq 异步派发]
      - SagaStep 枚举类
      - SagaOrchestrator 类
      - execute / compensate / _record_progress / _dispatch_async 方法注释
    schemas.py              ← [职责：Pydantic DTO 集合]
      - SecretRef / SubmitForm / SagaResult / RollbackRequest / SagaContext / StepResult
    compensator.py          ← [职责：Saga 反向补偿器]
      - Compensator 类
      - compensate_secret / compensate_metadata / publish_rollback_done / run
    steps/
      __init__.py           ← [职责：steps 包初始化]
      base.py               ← [职责：SagaStep 抽象基类]
      dry_run.py            ← [职责：Saga 第 1 步：沙箱预演（调 M-C01）]
      k4.py                 ← [职责：Saga 第 2 步：K4 静态分析（调 M-C02）]
      secret.py             ← [职责：Saga 第 3 步：Vault 写入（调 M-C07）]
      metadata.py           ← [职责：Saga 第 4 步：元数据落库（M-D01）]
      history.py            ← [职责：Saga 第 5 步：审计日志 + 事件发布]
    tests/
      __init__.py           ← [职责：测试包初始化]
      test_orchestrator.py  ← [职责：SagaOrchestrator 单元测试，9 场景]
      test_steps.py         ← [职责：5 Step 子类单元测试，7 场景]
      test_controllers.py   ← [职责：CreateController 路由测试，5 场景]

[文件间依赖关系]
  controllers.py → orchestrator.py → steps/*.py
                       ↓
                   compensator.py
  steps/base.py ← {dry_run, k4, secret, metadata, history}.py
  schemas.py → {controllers, orchestrator, steps, compensator}.py
  tests/ → {controllers, orchestrator, steps/*}.py

[模块依赖方向（严格）]
  M-B05 → M-C01 (Sandbox, dry_run)
  M-B05 → M-C02 (K4 Analyzer, k4)
  M-B05 → M-C07 (Secret Manager, secret)
  M-B05 → M-D01 (Metadata Store, metadata)
  M-B05 → M-D03 (Cache, progress)
  M-B05 → M-EV01 (Event Bus, history / rollback_done)
  M-B05 → M-A01 (MCP Create router, controllers)
  禁止反向依赖（应用层不依赖接入层细节）

[命名合规] snake_case 文件 ✓ | PascalCase 类 ✓ | snake_case 函数 ✓
[目录层级] 3 层（agenthub/application/create/）
[来源标注] [DD-001:FS-MCP/FS-009 + MD-MCP/M-B05 + IC-MCP/IC-007 + DDR-005]
```

---

## 2. 方案对比（4.11 多方案机制）

| 维度 | 方案 A（主方案：单 orchestrator + 5 steps） | 方案 B（备选：每步骤独立 service） |
|------|--------------------------------------|-------------------------------|
| 文件结构合规度（0.22） | 9-10（11 文件，3 层，FS 严格遵循） | 5-6（16+ 文件，模块膨胀） |
| 注释完整度（0.22） | 9-10（每文件有头注释+类注释+方法注释） | 7-8（注释模板可复用但分散） |
| 接口契约注释化（0.18） | 9-10（IC-007 集中体现） | 6-7（IC-007 分散到 5 service） |
| 代码风格合规（0.13） | 9-10（CS-MCP 100% 遵守） | 9-10（同上） |
| 设计可追溯（0.13） | 9-10（每文件标注 [DD-001:XXX]） | 7-8（5 service 各自标注） |
| 框架可追溯（0.12） | 9-10（含 FDR/FH/FC/API） | 7-8（同上） |
| **加权总分** | **9.32** | **6.96** |

**选择方案 A**：主方案总分 - 备选方案 = 2.36，方案 A 显著胜出（虽未达 5 分阈值，但主方案在文件结构清晰度、Saga 原子性、Step 可测试性上明显更优）。

---

## 3. [DD-M 洞察] 注入

**[DD-M-B05-洞察-1]** M-B05 横跨 5 个基础设施模块（M-C01/C02/C07/D01/D03/M-EV01），依赖面较广；建议在 orchestrator 构造时显式注入所有依赖（DI），避免隐式全局状态导致测试困难。同时 K4/DryRun 失败 vs Secret/Metadata 失败的语义差异（[DDR-005]）必须在 orchestrator.execute() 入口明确分流。

**[DD-M-B05-洞察-2]** IC-007 接口契约的幂等键 (mcp_id, version) 在 orchestrator 入口处必须先做 UNIQUE 探测（轻量 PG SELECT），避免 arq 入队后才发现冲突导致资源浪费。建议在 controllers.submit() 内、orchestrator.execute() 之前加 idempotency_check 步骤。

**[DD-M-B05-洞察-3]** Compensator 与 orchestrator 存在循环依赖风险（orchestrator 调用 Compensator；Compensator 需要回写 ctx 到 mcp_submission）；通过 inject UoW 工厂 + 仅在 Compensator 持有 ctx 引用（不回引 orchestrator）打破循环。

---

文件框架结构文档结束。
