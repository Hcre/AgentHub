# 详细设计文档 DD-MCP-V1.0-20260602

> 项目代号：MCP（Model Context Protocol AgentHub）
> 版本：V1.0  · 日期：2026-06-02
> 角色：DD-001 详细设计师（总）
> 上游：AR-001（ARI = 0.964，已通过门禁）
> 下游：DD-M（详细设计师·模块，22 名按 M-NNN 并行分工）
> 目标：DDI ≥ 0.90

---

## 0. AR 方案接收质量门禁（soul 4.10）

| 校验项 | 校验规则 | 实测 | 结论 |
|--------|--------|------|------|
| 方案完整性 | AR 10 类产出物 | 10/10（TA/AC/TS/API/DP/PO/SEC/TD/TDR/AH） | 通过 |
| 方案收敛度 | ARI ≥ 0.85 | ARI = 0.964 | 通过 |
| 模块覆盖 | 22 模块均有技术选型 | 100%（22/22） | 通过 |
| 接口规范完整 | 28 IF 全部含 API-NNN + 兼容性矩阵 | 100%（28/28） | 通过 |
| 技术选型明确 | 30 TS 锁定版本 | 100%（无 latest） | 通过 |
| 部署方案完整 | DP 含组件 / 资源 / 启动顺序 / 健康检查 | 完整 | 通过 |
| 澄清请求数 | ≤ 3 | 0 | 通过 |

**门禁结论：通过，进入详细设计流程。**

---

## 1. 全局设计识别（L0 / D1 产出，模板 A）

### 1.1 设计主题分类（22 模块 + 30 TS 全覆盖）

| 设计主题 | 包含模块 | 核心特征 | 选定设计模式 |
|---------|---------|---------|---------|
| CRUD 型 · 持久化 | M-D01 | 30 DE / 35 表 / 强一致事务 | Repository + UnitOfWork |
| IO 密集 · 网关 | M-A01 / M-A02 / M-A03 | 路由 / 限流 / 鉴权 / 协议转换 | Adapter + Chain + Decorator |
| 协调型 · 调度 | M-A04 | Leader 选举 + Cron + 状态机 | State Machine + Observer |
| 业务核心 · Service | M-B01 / M-B03 / M-B04 | FastAPI 业务编排 | Service Layer + Strategy |
| 业务核心 · Saga 编排 | M-B05 / M-C09 | 多步骤链 + 补偿 | Saga + Compensation |
| 生命周期 · 进程池 | M-B02 | spawn/health/recycle/evict 状态机 | Object Pool + State Machine + Factory |
| 沙箱 · 跨平台适配 | M-C01 | 4 后端（cgroup / sandbox-exec / JobObj / Docker） | Adapter + Strategy + Factory |
| 规则引擎 · 静态分析 | M-C02 | 11+1 类 AST 模式 + gRPC 8 worker | Strategy + Template Method |
| 纯函数 · 转换 | M-C03 / M-C08 | 模板深合并 / 命名转换 | Pure Function + Value Object |
| 安全代理 · 5 层防御 | M-C04 / M-C05 / M-C06 / M-C07 | DNS Pin / ACL / SSRF / Secret | Proxy + Chain of Responsibility |
| 时序 / 日志 | M-D02 | Pull-Prom + Push-Loki | Observer + Pub/Sub |
| 缓存 / 队列 | M-D03 | Redis cluster KV / Stream / PubSub | Cache Proxy + Flyweight |
| 事件总线 | M-EV01 | 5 topic 跨进程分发 | Event Bus + Pub/Sub |

**[DD 洞察-1]** M-B02 进程池与 M-C01 沙箱共用 64/ws 硬限，跨实例并发 spawn 依赖 PG row-lock + workspace 槽位预占。若 PG 主库故障，spawn 请求将全 timeout。在 MD-006 / MD-010 模块细化中已纳入 Redis Redlock（5 节点）作为降级路径（呼应 [AR洞察-2]）。

**[DD 洞察-2]** M-C03 模板引擎与 M-C08 命名转换被标注"纯函数 in-proc"，但 M-C03 实际会读 `mcp-config` 文件做深合并；若不通过类型签名强制 in-process 调用，未来易被错误重构为远程服务，性能从 < 5ms 退化到 50ms+。CS 风格指南已增加 `@pure` / `@in_process_only` 装饰器规范约束。

**[阶梯退出检查]** ①全部 22 M 已分类: 是 ②全部 28 API 已分类: 是 ③D1 = 100%

---

## 2. 设计模式选择 + 多方案对比（L1 / D2-D6 产出，模板 B）

### 2.1 核心设计模式选择（基于 soul 4.8 决策树）

| 设计模式 | 选择理由 | 适用模块 | 模式约束（soul 4.8.2） |
|---------|---------|---------|---------|
| Repository + UnitOfWork | 30 DE / 强一致 / 事务边界明确 | M-D01 | 每实体对应一个 Repository；UnitOfWork 控制事务 |
| Service Layer | FastAPI 业务编排 | M-B01 / M-B03 / M-B04 | Controller→Service→Repository 严格三层，禁止跨层 |
| Saga + Compensation | M-B05 五步链 / M-C09 长事务 | M-B05 / M-C09 | 每步骤定义 forward + compensate |
| Object Pool + State Machine | M-B02 进程池生命周期 | M-B02 | 状态: idle→spawning→running→idle→recycled |
| Adapter + Strategy + Factory | M-C01 跨平台沙箱 | M-C01 | `SandboxBackend` 接口统一 4 后端 |
| Strategy + Template Method | M-C02 K4 11+1 类规则 | M-C02 | `Rule` 接口 + `ASTAnalyzer` 模板 |
| Proxy + Chain of Responsibility | SSRF 5 层防御 | M-C04 / M-C05 / M-C06 | `URLValidator` 链式校验 |
| Cache Proxy + Decorator | Redis allowlist / dns 缓存 | M-B04 / M-C04 | `RepositoryDecorator` 透明缓存，TTL 强制 |
| Event Bus + Pub/Sub | 22 Agent 跨进程通信 | M-EV01 | 同 topic fan-out；关键 topic 用 Stream（[AR洞察-1]） |
| Observer | Cron 触发 → 多消费方 | M-A04 | publish `trigger.cron.fired` |
| Pure Function + Value Object | M-C03 / M-C08 | 强制 in-proc，无 IO | `@pure` / `@in_process_only` 装饰器 |

### 2.2 方案对比（soul 4.11，7 维度加权）

| 对比维度 | 权重 | 主方案 A：分层 + Repository + Saga + 事件总线 | 备选方案 B：Hexagonal + CQRS + 事件溯源 | A 得分 | B 得分 |
|---------|------|---------|---------|------|------|
| 模块细化完整度 | 0.15 | 高（22 模块均通过 7/7 细化） | 中（CQRS 双模型增加未覆盖类） | 9 | 6 |
| 接口契约清晰度 | 0.15 | 高（22 IC 含幂等性/前置后置/并发安全） | 中（命令/查询双 IC 复杂度高） | 9 | 6 |
| 数据结构设计 | 0.15 | 高（30 DS 含 DE/索引/约束/分片） | 中（事件溯源需事件存储 + 快照表） | 9 | 5 |
| 文件结构规范 | 0.15 | 高（标准 FastAPI 包布局） | 中（多 bounded context 包膨胀） | 8 | 6 |
| 代码风格覆盖 | 0.10 | 高（ruff + black + mypy + .editorconfig + .pre-commit） | 高（同主方案） | 9 | 9 |
| 异常处理完整 | 0.15 | 高（14 SEC → 14 EX 全覆盖 + 通用降级矩阵） | 高（同主方案） | 9 | 9 |
| 设计可追溯性 | 0.15 | 高（100% [AR:.../DD推断:...]） | 高（同主方案） | 9 | 9 |
| **加权总分** | 1.00 | | | **8.85** | **7.05** |

**[选择理由]**
主方案 A 总分 8.85 vs 备选 B 7.05，加权差值 1.80。原始 100 分制换算后差值 18 ≥ 5（soul 4.11 阈值），主方案显著胜出。备选 B 的 CQRS + 事件溯源对 V1.0 单团队 22 模块、强一致 PG 场景属过度设计（违反 R14 禁止过度设计）。主方案与 AR-001 ADR-001 / ADR-003 决策一致。

**[DD 洞察-3]** 主方案中 M-B05 / M-C09 选 Saga，但 Saga 补偿事务必须可执行——M-B05 的 K4 分析步骤（API-210）失败后无法"撤销"。已在 MD-009 模块细化中明确：K4 失败 → 标记 `mcp_submission.status = rejected`（无需补偿，因尚未对外可见），并记 `DDR-005`。

**[阶梯退出检查]**
①设计模式已选定: 是（11 套模式）
②2 个方案已草拟: 是
③对比已完成: 是
④D2 = 95%（22 M 全通过 7/7 细化）
⑤D6 = 100%（30 TS 全覆盖风格指南）

---

## 3. 22 模块编号分配（供 DD-M 并行分工）

| 模块 ID | 名称 | 设计模式 | 细化方案路径 | DD-M 实例 |
|--------|------|---------|---------|---------|
| M-A01 | Web API Gateway | Adapter + Chain + Decorator | MD-MCP-V1.0-20260602.md#M-A01 | DD-M-01 |
| M-A02 | WS Event Gateway | Observer + Adapter | MD-MCP-V1.0-20260602.md#M-A02 | DD-M-02 |
| M-A03 | Webhook Receiver | Chain of Responsibility | MD-MCP-V1.0-20260602.md#M-A03 | DD-M-03 |
| M-A04 | Cron Scheduler | State Machine + Observer | MD-MCP-V1.0-20260602.md#M-A04 | DD-M-04 |
| M-B01 | Market Service | Service Layer + Repository | MD-MCP-V1.0-20260602.md#M-B01 | DD-M-05 |
| M-B02 | Process Pool Manager | Object Pool + State Machine | MD-MCP-V1.0-20260602.md#M-B02 | DD-M-06 |
| M-B03 | Binding Engine | Service Layer + Strategy | MD-MCP-V1.0-20260602.md#M-B03 | DD-M-07 |
| M-B04 | Approval Engine | Service + Cache Proxy | MD-MCP-V1.0-20260602.md#M-B04 | DD-M-08 |
| M-B05 | MCP Create | Saga + Compensation | MD-MCP-V1.0-20260602.md#M-B05 | DD-M-09 |
| M-C01 | Sandbox Engine | Adapter + Strategy + Factory | MD-MCP-V1.0-20260602.md#M-C01 | DD-M-10 |
| M-C02 | K4 Analyzer | Strategy + Template Method | MD-MCP-V1.0-20260602.md#M-C02 | DD-M-11 |
| M-C03 | Template Engine | Pure Function + Value Object | MD-MCP-V1.0-20260602.md#M-C03 | DD-M-12 |
| M-C04 | DNS Pinning | Cache Proxy + Singleton | MD-MCP-V1.0-20260602.md#M-C04 | DD-M-13 |
| M-C05 | Network ACL | Strategy + Adapter | MD-MCP-V1.0-20260602.md#M-C05 | DD-M-14 |
| M-C06 | SSRF Guard | Chain of Responsibility | MD-MCP-V1.0-20260602.md#M-C06 | DD-M-15 |
| M-C07 | Secret Manager | Proxy + Cache Proxy | MD-MCP-V1.0-20260602.md#M-C07 | DD-M-16 |
| M-C08 | Name Transformer | Pure Function | MD-MCP-V1.0-20260602.md#M-C08 | DD-M-17 |
| M-C09 | ACL Migration | Saga + Compensation | MD-MCP-V1.0-20260602.md#M-C09 | DD-M-18 |
| M-D01 | Metadata Store | Repository + UnitOfWork | MD-MCP-V1.0-20260602.md#M-D01 | DD-M-19 |
| M-D02 | TS & Log | Observer + Pub/Sub | MD-MCP-V1.0-20260602.md#M-D02 | DD-M-20 |
| M-D03 | Cache & Queue | Cache Proxy + Flyweight | MD-MCP-V1.0-20260602.md#M-D03 | DD-M-21 |
| M-EV01 | Event Bus | Event Bus + Pub/Sub | MD-MCP-V1.0-20260602.md#M-EV01 | DD-M-22 |

---

## 4. 设计自评审（soul 4.9）

| 评审项 | 通过条件 | 实测 |
|--------|--------|------|
| 模块细化完整（7/7） | 22 模块均通过 | 22/22 ✓ |
| 接口契约完整 | 22 IC 覆盖 28 API 跨进程/外部 | 100% ✓ |
| 数据结构完整 | 30 DS 覆盖 30 DE / 5 MVIEW | 100% ✓ |
| 文件结构规范 | 22 模块有 FS | 22/22 ✓ |
| 代码风格完整 | 30 TS 有风格指南 | 100% ✓（含 ruff/black/mypy/.editorconfig） |
| 异常处理覆盖 | 14 SEC 有 EX | 14/14 ✓ |
| 设计模式一致 | 模式约束遵守 | ✓ |
| DDR 完整 | 重大决策记录 | 12/12 ✓ |
| 可追溯性 | 100% 标注 | ✓ |
| 洞察覆盖率 | 设计风险已覆盖 | 12 条 DD 洞察 |
| 方案对比完整 | 主+备+对比 | ✓ |
| 接口契约验收（4.12） | 6 项检查通过 | 22/22 ✓ |
| 文件结构可实现 | 符合 FastAPI 最佳实践 | ✓ |
| 并发安全 | 所有接口考虑 | ✓（IC 含幂等性 + 并发安全字段） |
| 风格指南可执行 | 含自动化工具配置 | ✓（pyproject.toml + .pre-commit-config.yaml） |

**15/15 自评审通过 ✓**

---

## 5. DDI 综合指数

详见 `DH-MCP-V1.0-20260602.md`。

**DDI = 0.952 ≥ 0.90 ✓ 已收敛，可交付 DD-M。**

---

**详细设计文档结束。**
