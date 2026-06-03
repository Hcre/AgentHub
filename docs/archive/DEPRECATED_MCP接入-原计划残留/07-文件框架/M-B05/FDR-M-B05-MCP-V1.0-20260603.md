# 框架决策记录 FDR-M-B05-MCP-V1.0-20260603

> M-B05 文件框架重大决策记录 | 来源 [DD-001:MD-MCP/M-B05 + DDR-005 + DDR-002 + IC-MCP/IC-007]
> 5 条 FDR 全部已接受

---

## FDR-B05-001 steps 子包独立 vs 扁平化

```
[决策编号] FDR-B05-001
[决策标题] 5 个 Step 拆分为 steps/ 子包
[决策状态] 已接受
[决策内容] 5 个 Step 子类（DryRunStep/K4Step/SecretStep/MetadataStep/HistoryStep）放入 steps/ 子包，而非扁平放在 create/ 根目录
[决策理由]
  - 5 步清晰分组，未来若新增 ApprovalStep/CleanupStep 等可继续放入
  - steps/base.py 抽象基类仅与 steps/ 内文件耦合，外部不感知
  - 与 M-C09 ACL Migration 步骤拆分（FS-018）保持一致风格
[拒绝的替代方案] 扁平化 5 个文件：文件散乱，难以发现步骤边界
[影响范围] M-B05 + steps/ 内部 7 个文件
[相关FDR] 无
[来源标注] [DD-M推断:文件组织一致性原则 + FS-018 类比]
```

---

## FDR-B05-002 Saga 5 步顺序固化在 orchestrator

```
[决策编号] FDR-B05-002
[决策标题] Saga 步骤顺序由 orchestrator 集中定义
[决策状态] 已接受
[决策内容] SagaStep 枚举 ORDER = (DRY_RUN, K4, SECRET, METADATA, HISTORY) 在 orchestrator.py 内定义，steps/* 子类不感知顺序
[决策理由]
  - 步骤顺序是 Saga 业务规则，集中在编排器便于审计
  - steps/base.py 仅抽象 forward/compensate 接口，零业务顺序假设
  - 测试时可独立测单个 step 而无需关心上下文链
[拒绝的替代方案] 步骤顺序由步骤自身 next_step 引用：循环依赖风险，违反 [DD-M-B05-洞察-3]
[影响范围] orchestrator.py + steps/* 6 个文件
[相关FDR] FDR-B05-001
[来源标注] [DD-001:MD-MCP/M-B05 + IC-MCP/IC-007]
```

---

## FDR-B05-003 Compensator 仅持有 ctx 引用，回避循环

```
[决策编号] FDR-B05-003
[决策标题] Compensator 不回引 SagaOrchestrator
[决策状态] 已接受
[决策内容] Compensator.run(trace_id, failed_step) 仅接收 ctx 与 failed_step；不回引 orchestrator 实例；通过参数传递 + UoW 工厂注入打破循环
[决策理由]
  - [DD-M-B05-洞察-3] 已识别 orchestrator ↔ compensator 循环依赖风险
  - Compensator 持 UoW 工厂 + VaultClient + EventBus 即可完成所有补偿动作
  - 单测时可独立 mock 三个依赖
[拒绝的替代方案] 双向引用 + 回调：测试困难 + 循环
[影响范围] compensator.py + orchestrator.py
[相关FDR] FDR-B05-001
[来源标注] [DD-M推断:依赖注入解耦 + 循环依赖避免]
```

---

## FDR-B05-004 K4/DryRun 无补偿（遵循 DDR-005）

```
[决策编号] FDR-B05-004
[决策标题] K4/DryRun 步骤在 SagaStep 基类默认 no-op 补偿
[决策状态] 已接受
[决策内容] steps/base.py 中 SagaStep.compensate() 默认 no-op；K4Step/DryRunStep 不重写；orchestrator.execute() 在 K4/DryRun 失败时直接标 rejected 不调用 compensator
[决策理由]
  - [DDR-005] 已明确 K4 是无副作用分析步骤，撤销无意义
  - SagaStep 基类默认 no-op 避免子类重复实现
  - orchestrator 集中控制何时调用 compensator
[拒绝的替代方案] K4/DryRun 各自实现空 compensate：冗余代码
[影响范围] steps/base.py + orchestrator.py + steps/k4.py + steps/dry_run.py
[相关FDR] FDR-B05-002
[来源标注] [DD-001:DDR-005]
```

---

## FDR-B05-005 history 失败仅告警不补偿

```
[决策编号] FDR-B05-005
[决策标题] HistoryStep 失败不进入补偿链
[决策状态] 已接受
[决策内容] history 是 Saga 最后一步，业务已完成；失败仅重试 3 次 + ERROR 告警，不调用 Compensator
[决策理由]
  - history 写入 mcp_submission_history 表（DS-013 append-only）
  - 即便 history 失败，mcp_submission 表 status=done 已生效，业务侧成功
  - 重试 3 次后仍失败说明 EventBus/UoW 故障，触发 CRITICAL 告警
[拒绝的替代方案] history 失败也回滚 mcp_submission：导致业务已上线的 MCP 突然消失，回滚伤害更大
[影响范围] steps/history.py + orchestrator.py
[相关FDR] FDR-B05-002
[来源标注] [DD-001:MD-MCP/M-B05 + DS-MCP/DS-013]
```

---

## FDR 统计

| FDR | 状态 | 影响文件 |
|-----|------|---------|
| FDR-B05-001 | 已接受 | steps/ 7 文件 |
| FDR-B05-002 | 已接受 | orchestrator.py + 6 step 文件 |
| FDR-B05-003 | 已接受 | compensator.py + orchestrator.py |
| FDR-B05-004 | 已接受 | steps/base.py + orchestrator.py + 2 step |
| FDR-B05-005 | 已接受 | steps/history.py + orchestrator.py |
| **总数** | **5** | **11 文件** |

---

框架决策记录文档结束。
