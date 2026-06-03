# FDR-M-D01-MCP-V1.0-20260603 框架决策记录

> [模块编号] M-D01 Metadata Store
> [DD-M] DD-M-D01-20260603

---

## FDR-MD01-001 Specification 命名空间隔离

```
[决策编号] FDR-MD01-001
[决策标题] Specification 模式归入 repositories/ 子包而非顶层
[决策状态] 已接受
[决策内容]
  将 Specification 基类与具体规约统一放在
  `src/agenthub/data/metadata/repositories/specifications.py`，
  而非放到顶层 `metadata/specifications.py`。
[决策理由]
  1. Specification 仅服务 Repository 查询，是 Repository 模式的辅助类型，归入同子包语义清晰
  2. 避免与 application/binding/strategies.py 等业务策略命名冲突（DD-M 洞察）
  3. 跨模块 import 路径更短：`from agenthub.data.metadata.repositories import PendingInboxByWorkspaceSpec`
[拒绝的替代方案]
  方案 B：独立 `specifications/` 子包，每个规约一文件
    拒绝理由：5 个规约文件碎片化，未来增长 ≤ 20 个规约属合理范围，单文件足够
[影响范围]
  - repositories/specifications.py 单文件承载基类 + 5 常用规约
  - repositories/__init__.py 重新导出
[相关 FDR] 无
[来源标注] [DD-M推断:依据=DDD Specification 模式归属 Repository 子领域]
```

---

## FDR-MD01-002 Repository 按业务域聚合到 5 文件

```
[决策编号] FDR-MD01-002
[决策标题] 19 Repository 按业务域聚合到 5 个文件（而非 19 个独立文件）
[决策状态] 已接受
[决策内容]
  19 Repository 类按业务域聚合到 5 个 *_repos.py：
    - market_repos.py:    MCPServer / MCPInstallation / Workspace / UserBinding
    - pool_repos.py:      ProcessPool / HealthHistory
    - approval_repos.py:  InboxQueue / InboxDecision / Allowlist30d
    - submission_repos.py:MCPSubmission / MCPSubmissionHistory / WSSubscription
    - system_repos.py:    Cron / K4 / ACL / Secret / MigrationHistory（7 类）
[决策理由]
  1. 同域 Repository 经常共同使用（如 InboxQueue + InboxDecision + Allowlist 在 decide 流程内）
     聚合到同文件便于阅读与重构
  2. 单文件 Repo 数 ≤ 7（< soul 上限 20 函数），合规
  3. DD-S 阶段可按需进一步拆分；本阶段优先收敛文件碎片
  4. 与 models/ 个文件方案不同：模型 1:1 表，独立文件便于 Alembic 反向工程
[拒绝的替代方案]
  方案 B：每个 Repository 独立文件（19 个 *.py）
    拒绝理由：文件碎片化，import 路径冗长，业务理解需在 19 文件间跳转
[影响范围]
  - repositories/ 子包：5 业务文件 + base + specifications + __init__ = 8 文件
  - 测试文件按业务域配套（test_approval_repos / test_pool_repos）
[相关 FDR] FDR-MD01-001
[来源标注] [DD-M推断:依据=Cohesion over Splitting + 单文件 ≤ 20 函数合规]
```

---

## FDR-MD01-003 AppendOnly 双重防护（ORM event + PG trigger）

```
[决策编号] FDR-MD01-003
[决策标题] InboxDecision / SubmissionHistory / MigrationHistory 采用 ORM event + PG trigger 双重防护
[决策状态] 已接受
[决策内容]
  对 DS-010 / DS-013 / DS-019 三张 append-only 表：
  1. 应用层：AppendOnlyMixin 通过 SQLAlchemy event listener 拦截 'before_update' / 'before_delete'，抛 AppendOnlyViolation
  2. DB 层：Alembic 迁移创建 PG TRIGGER 'before_update'/'before_delete' RAISE EXCEPTION
[决策理由]
  1. 应用层防护：阻止 ORM 用户调用 update/delete，提供清晰错误信息
  2. DB 层防护：阻止 raw SQL / psql / pgAdmin 等绕过 ORM 的修改路径
  3. 与 [DD洞察-5]（GDPR right to erasure）兼容：未来添加 redacted=true 标记列，
     提供运维接口 mark_redacted() 软删而非物理删
[拒绝的替代方案]
  方案 B：仅 ORM event 拦截
    拒绝理由：raw SQL / 运维直接 psql 可绕过；审计完整性不可保证
  方案 C：仅 PG trigger
    拒绝理由：应用层错误信息不友好（PG 触发异常字符串）
[影响范围]
  - models/base.py::AppendOnlyMixin
  - models/inbox_decision.py / mcp_submission_history.py / mcp_migration_history.py 继承
  - Alembic 迁移需手写 op.execute("CREATE TRIGGER ...")
  - 测试 test_models_appendonly.py 验证两层防护
[相关 FDR] 无
[来源标注] [DD-001:DS-010/013/019 + DD洞察-5]
```

---

## FDR-MD01-004 Deadlock 自动重试装饰器封装到 BaseRepository

```
[决策编号] FDR-MD01-004
[决策标题] Deadlock 重试装饰器作为 BaseRepository 内部机制，对调用方透明
[决策状态] 已接受
[决策内容]
  DeadlockError (SQLSTATE 40P01) 自动重试 max 3 次（100/200/400ms 退避）
  作为 BaseRepository 装饰器 _retry_on_deadlock，对调用方透明
  超限上抛 DBDeadlockExhausted，调用方决定是否上抛 503
[决策理由]
  1. PG Deadlock 是数据库层瞬时错误，业务层重复实现重试逻辑造成 DRY 违反
  2. 内置重试与 IC-017 [DB_DEADLOCK 503 - 重试 max 3] 契约完全对齐
  3. 单次最大额外延迟 700ms，仍在 P95 ≤ 50ms（PK 查询）+ 一般业务 < 1s 范围内
[拒绝的替代方案]
  方案 B：由业务层 services 自行 catch + retry
    拒绝理由：22 模块 services 重复实现，DRY 严重违反；易遗漏
  方案 C：仅在 UnitOfWork 层重试（整事务 retry）
    拒绝理由：整事务 retry 副作用难以保证幂等；细粒度 method retry 更安全
[影响范围]
  - repositories/base.py::_retry_on_deadlock 装饰器
  - 所有 add/update/delete/select_for_update 方法装饰
[相关 FDR] 无
[来源标注] [DD-001:IC-017 错误码 + DD-M推断:DRY 重试封装]
```

---

## FDR-MD01-005 process_pool 部分唯一索引手写迁移

```
[决策编号] FDR-MD01-005
[决策标题] DS-004 partial UNIQUE 索引 Alembic 手写迁移（不依赖 autogenerate）
[决策状态] 已接受
[决策内容]
  process_pool 表的部分唯一索引
    UNIQUE (workspace_id, mcp_id) WHERE state IN ('running','idle')
  通过 Alembic op.execute() 手写 CREATE UNIQUE INDEX ... WHERE ...
  而非 autogenerate（autogenerate 不支持 partial unique）
[决策理由]
  1. Alembic autogenerate 对 PG partial unique 支持不足，会生成无 WHERE 的完整唯一约束，导致同 ws 同 mcp 永远只能存在一行
  2. 手写迁移保证语义精确：仅 running/idle 状态唯一，recycled/zombie 可共存历史行
[拒绝的替代方案]
  方案 B：表级 UNIQUE 不带 WHERE
    拒绝理由：违反业务（recycled 历史行影响后续 spawn 唯一性校验）
  方案 C：业务层校验
    拒绝理由：并发场景失效，必须 DB 级约束
[影响范围]
  - migrations/versions/xxx_create_process_pool.py 含手写 CREATE INDEX
  - models/process_pool.py 注释提示
[相关 FDR] 无
[来源标注] [DD-001:DS-004 + Alembic 文档 limitations]
```

---

## FDR-MD01-006 Repository 内不允许 commit/rollback

```
[决策编号] FDR-MD01-006
[决策标题] Repository 模式强约束：仅数据访问，事务由 UnitOfWork 唯一控制
[决策状态] 已接受
[决策内容]
  BaseRepository 与 17 具体 Repository 严禁出现 session.commit() / session.rollback()
  事务边界 100% 由 `async with UnitOfWork(engine) as uow:` 控制
[决策理由]
  1. 经典 Repository + UnitOfWork 模式约束（[设计模式约束: soul 4.8.2]）
  2. 业务层调用多个 Repository 操作时，需要在同一事务内原子提交（如 decide 流程）
  3. 避免 nested transaction 与 savepoint 复杂度
[拒绝的替代方案]
  方案 B：Repository 内 commit（"自治事务"）
    拒绝理由：失去跨 Repository 原子性；违反 UoW 模式
[影响范围]
  - 静态检查：CI grep "session.commit\|session.rollback" repositories/ → 必须为空
  - 测试 test_base_repository.py::test_select_for_update_when_outside_uow_then_raises_runtime_error
[相关 FDR] 无
[来源标注] [设计模式: Repository + UnitOfWork 约束 + DD-001:MD:M-D01]
```

---

**FDR 记录总数：6 个** ✓（含 6 大重要决策，覆盖命名 / 文件组织 / append-only / Deadlock / 索引 / 事务边界）

**[来源标注]** [DD-001:MD:M-D01 + DS-001~019 + IC-017 + 设计模式 Repository+UnitOfWork+Specification]

**框架决策记录文档结束。**
