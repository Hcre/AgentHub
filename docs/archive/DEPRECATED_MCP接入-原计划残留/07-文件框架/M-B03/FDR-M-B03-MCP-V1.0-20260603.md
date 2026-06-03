# 框架决策记录 FDR-M-B03-MCP-V1.0-20260603

> M-B03 Binding Engine 框架决策记录
> 来源 [soul 4.13 + DD-001:FS-007]

---

## FDR-B03-001 引入 L4 单一源 ConfigGenerator

```
[决策编号] FDR-B03-001
[决策标题] 将 mcp-config 写盘入口收敛到 ConfigGenerator
[决策状态] 已接受
[决策内容] 强制所有 mcp-config 文件生成经 ConfigGenerator，禁止任何模块/类直接 open() 该文件
[决策理由] ADR-005 明确要求 L4 单一源；M-B02 spawn 与 M-B03 bind 共用同一文件，源头不统一会引发多 writer 竞争
[拒绝的替代方案]
  备选1: 在 services.py 内联文件 IO - 拒绝理由：违反 ADR-005 单一源，且 fcntl 锁逻辑分散
  备选2: 用 mmap - 拒绝理由：不支持 fcntl.flock，且与 os.replace atomic 语义不兼容
[影响范围] generators.py / services.py / 后续所有 binding 流程
[相关FDR] FDR-B03-004
[来源标注] [DD-001:ADR-005 + SEC:SEC-011]
```

## FDR-B03-002 状态机简化（5 → 4 步）

```
[决策编号] FDR-B03-002
[决策标题] binding 状态机精简为 Pending/ConfigGenerated/Spawned/Active/Released
[决策状态] 已接受
[决策内容] 沿用 MD-MCP#M-B03 的状态机定义；DS-002 表 schema 中 status 字段对应
[决策理由] 与 DS-002 mcp_installations 字段对齐；Released 终态无需独立记录
[拒绝的替代方案]
  备选1: 完整 7 态机（含 InitValidating / SpawnReserved / Evicting） - 拒绝理由：与 M-B02 spawn 状态机耦合过深
[影响范围] services.py / repository.py
[相关FDR] (无)
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
```

## FDR-B03-003 Strategy 默认实现选择 DefaultMappingStrategy

```
[决策编号] FDR-B03-003
[决策标题] 当用户未提供 mapping 时使用 DefaultMappingStrategy
[决策状态] 已接受
[决策内容] 1:1 映射 + M-C08 命名规范化（6→8 hex）
[决策理由] 与 ADR-007 命名转换规则一致；零配置场景下用户期望即开即用
[拒绝的替代方案]
  备选1: 强制要求 mapping 必填 - 拒绝理由：增加 1:1 场景摩擦
  备选2: 用 hash(name) 而非 M-C08 - 拒绝理由：未走命名空间映射，碰撞处理不一致
[影响范围] strategies.py / services.py
[相关FDR] (无)
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + ADR-007]
```

## FDR-B03-004 锁竞争重试策略（重试 1 次 + 200ms）

```
[决策编号] FDR-B03-004
[决策标题] ConfigLockTimeout 后 sleep(0.2) 重试 1 次
[决策状态] 已接受
[决策内容] fcntl 锁竞争 → ConfigLockTimeoutError → 200ms 后重试 1 次 → 仍失败抛 503
[决策理由] EX-011 明确要求"重试 1 次（200ms）"；平衡响应延迟与成功率
[拒绝的替代方案]
  备选1: 指数退避 100/200/400ms × 3 - 拒绝理由：超过 EX-011 规范，500ms P95 性能约束不达标
  备选2: 不重试直接 503 - 拒绝理由：短抖动下用户体验差
[影响范围] services.py / generators.py
[相关FDR] FDR-B03-001
[来源标注] [DD-001:EX-MCP-V1.0-20260602#EX-011 + SEC:SEC-011]
```

## FDR-B03-005 跨模块调用走 in-proc（IC-004）

```
[决策编号] FDR-B03-005
[决策标题] BindingService → PoolAdapter.spawn 走 in-proc，不发布为 RPC
[决策状态] 已接受
[决策内容] 通过 IC-004 内部接口调用 M-B02，binding 与 spawn 强耦合，远程化收益<复杂度
[决策理由] M-B03 与 M-B02 同进程（同一应用容器），in-proc 性能优势明显；未来若需解耦可独立重构
[拒绝的替代方案]
  备选1: HTTP RPC - 拒绝理由：P95 退化 50ms+ ，违反 500ms 性能约束
  备选2: gRPC - 拒绝理由：同进程内 gRPC 无收益
[影响范围] services.py / __init__.py
[相关FDR] (无)
[来源标注] [DD-M推断:基于 in-proc 性能约束 + IC-004]
```
