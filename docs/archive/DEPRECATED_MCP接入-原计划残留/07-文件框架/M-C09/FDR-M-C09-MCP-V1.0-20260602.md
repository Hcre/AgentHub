# 框架决策记录 FDR-M-C09-MCP-V1.0-20260602

> M-C09 ACL Migration 重大框架决策记录
> 共 6 条 FDR

---

## FDR-001：采用 Saga + Compensation 而非 State Machine 单体

```
[决策编号] FDR-001
[决策标题] M-C09 采用 Saga + Compensation 模式
[决策状态] 已接受
[决策内容] M-C09 迁移流程采用 Saga 模式（4 步链 + 补偿器），而非单体状态机
[决策理由] 
  - 4 步之间无强耦合，每步可独立 mock / 单测
  - 补偿链清晰，便于审计
  - 与 M-B05 Saga 模式保持一致（[DD-001:MD-MCP-M-B05]）
[拒绝的替代方案] 
  - 替代方案 A：单体状态机（一个类含 4 状态 + 转移函数）
    拒绝理由：单文件 > 300 行；测试困难；与 M-B05 设计不一致
[影响范围] M-C09 全部文件
[相关FDR] FDR-002, FDR-003
[来源标注] [DD-001:MD-MCP-M-C09]
```

---

## FDR-002：步骤文件独立而非合并

```
[决策编号] FDR-002
[决策标题] 4 步独立文件（snapshot/apply/verify/commit）
[决策状态] 已接受
[决策内容] 每个 step 单独一个 .py 文件，配独立基类
[决策理由]
  - 单文件函数数 ≤ 20（[soul 4.2] 约束）
  - 4 步业务差异大，独立文件利于单测
  - DD-S 按文件并行开发互不阻塞
[拒绝的替代方案]
  - 替代方案 A：steps.py 单文件含 4 个类
    拒绝理由：超过单文件 20 函数上限；DD-001 FS-018 明确分文件
[影响范围] steps/ 目录
[相关FDR] FDR-001
[来源标注] [DD-001:FS-018]
```

---

## FDR-003：compensator 独立而非嵌入 orchestrator

```
[决策编号] FDR-003
[决策标题] 补偿器独立为 compensator.py
[决策状态] 已接受
[决策内容] 补偿逻辑独立到 Compensator 类，独立文件
[决策理由]
  - 补偿链是反向调用，独立后单测更简单
  - orchestrator 关注正向编排；comp 关注反向撤销；单一职责
  - 文件数增加 1，但每个文件 < 200 行，可维护性显著提升
[拒绝的替代方案]
  - 替代方案 A：补偿方法内联到 orchestrator
    拒绝理由：orchestrator 函数数会达 12+，接近 20 上限；测试矩阵翻倍
[影响范围] compensator.py
[相关FDR] FDR-001
[来源标注] [DD-M推断:关注点分离]
```

---

## FDR-004：leader 锁由调用方注入而非自建

```
[决策编号] FDR-004
[决策标题] leader 锁由调用方注入
[决策状态] 已接受
[决策内容] per-workspace leader 锁由 APScheduler / 触发方注入，orchestrator 不自建
[决策理由]
  - 调度器已有 leader 选举（M-A04 Cron Scheduler），避免重复实现
  - 单元测试可注入 mock 锁，避免真实 Redis 依赖
  - 符合 Dependency Inversion
[拒绝的替代方案]
  - 替代方案 A：orchestrator 内置 Redis SETNX
    拒绝理由：与 M-A04 重复；强依赖 Redis；测试需 fakeredis
[影响范围] orchestrator.__init__ 签名
[相关FDR] 无
[来源标注] [DD-M推断:DI + 单一职责]
```

---

## FDR-005：commit 步骤抛 NotCompensableError

```
[决策编号] FDR-005
[决策标题] commit 不可补偿（防御性抛错）
[决策状态] 已接受
[决策内容] CommitStep.compensate 抛 NotCompensableError；不执行任何撤销
[决策理由]
  - commit 是终态，写入 append-only 表后物理不可逆
  - 防御性抛错避免 silent bug（误以为已回滚）
  - 与 Saga 标准实践一致（终态步骤不可补偿）
[拒绝的替代方案]
  - 替代方案 A：commit 也可补偿（删除 history 记录）
    拒绝理由：违反 append-only；产生历史丢失问题
[影响范围] steps/commit.py
[相关FDR] FDR-001
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断]
```

---

## FDR-006：snapshot 步骤 compensate 为 no-op

```
[决策编号] FDR-006
[决策标题] snapshot 步骤补偿为 no-op
[决策状态] 已接受
[决策内容] SnapshotStep.compensate 不执行任何动作；快照本身是只读资产
[决策理由]
  - snapshot 仅写"读操作"——记录当前状态到表
  - 写历史表本身不应被撤销（append-only）
  - 真正的状态恢复由 snapshot 直接用于 apply.revoke + restore
[拒绝的替代方案]
  - 替代方案 A：删除 snapshot 记录
    拒绝理由：append-only；丢失审计
[影响范围] steps/snapshot.py
[相关FDR] FDR-003, FDR-005
[来源标注] [DD-M推断:snapshot 是非副作用步骤]
```

---

**框架决策记录文档结束。**
