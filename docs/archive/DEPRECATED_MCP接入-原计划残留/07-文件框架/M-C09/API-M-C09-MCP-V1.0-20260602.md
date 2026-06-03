# 接口注释清单 API-M-C09-MCP-V1.0-20260602

> M-C09 ACL Migration 接口契约注释清单
> 关联 IC-016（acl.migrate）
> 关联 API-280

---

## API-280-1 migrate（主入口）

```
[接口编号] API-280-1
[关联契约] IC-016
[实现文件] src/agenthub/infrastructure/acl_migration/orchestrator.py
[函数签名注释]
  async def migrate(
      workspace_id: uuid.UUID,           # [参数说明] 必填 工作空间 ID
      trace_id: Optional[uuid.UUID] = None  # [参数说明] 可选 追踪 ID
  ) -> MigrationResult:                  # [返回值说明] MigrationResult 含 result/applied_count/snapshot_hash
      """
      [函数职责] 执行 ACL 迁移完整 Saga 链
      
      Args:
          workspace_id: 目标工作空间 UUID
          trace_id: 追踪 ID；缺失时自动生成
      
      Returns:
          MigrationResult(result: 'committed'|'rolled_back',
                          applied_count: int,
                          snapshot_hash: str,
                          trace_id: UUID,
                          error_code: Optional[str])
      
      Raises:
          MIGRATION_VERIFY_FAILED: 验证阶段失败，已自动 rollback
          MIGRATION_APPLY_FAILED: 应用阶段失败，已 rollback 到 snapshot
          MIGRATION_SNAPSHOT_FAILED: 快照阶段失败，无可回滚
      
      Example:
          >>> result = await migrate(workspace_id=UUID("..."))
          >>> assert result.result in ("committed", "rolled_back")
      """
[来源标注] [DD-001:IC-016]
```

---

## API-280-2 schedule_migration（5min 周期入口）

```
[接口编号] API-280-2
[关联契约] IC-016
[实现文件] src/agenthub/infrastructure/acl_migration/orchestrator.py
[函数签名注释]
  async def schedule_migration(
      workspace_id: uuid.UUID           # [参数说明] 必填 工作空间 ID
  ) -> MigrationResult:                 # [返回值说明] 同 migrate
      """
      [函数职责] APScheduler 5min 周期触发入口
      
      Args:
          workspace_id: 目标工作空间 UUID
      
      Returns:
          MigrationResult
      
      Raises:
          MIGRATION_BUSY: per-ws leader 锁冲突
      
      Example:
          # 由 APScheduler 触发
          result = await schedule_migration(workspace_id=UUID("..."))
      """
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断:5min 周期入口]
```

---

## API-280-3 Compensator.execute

```
[接口编号] API-280-3
[关联契约] IC-016（补偿路径）
[实现文件] src/agenthub/infrastructure/acl_migration/compensator.py
[函数签名注释]
  async def execute(
      plan: CompensationPlan             # [参数说明] 必填 补偿计划
  ) -> bool:                             # [返回值说明] 全成功 True / 任一失败 False
      """
      [函数职责] 顺序执行补偿链
      
      Args:
          plan: 补偿计划（反向步骤链 + 原始 snapshot）
      
      Returns:
          bool: 全成功返回 True；任一 rollback 步骤失败返回 False
              （失败仅 WARN 记录，不抛异常中断后续步骤）
      
      Raises:
          无（内部异常被吞并记日志）
      
      Example:
          plan = compensator.build_plan(ws_id, completed_steps, snapshot)
          ok = await compensator.execute(plan)
      """
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断]
```

---

## API-280-4 Compensator.build_plan

```
[接口编号] API-280-4
[关联契约] IC-016
[实现文件] src/agenthub/infrastructure/acl_migration/compensator.py
[函数签名注释]
  def build_plan(
      workspace_id: uuid.UUID,                # [参数说明] 必填
      completed_steps: list,                   # [参数说明] 必填 已成功步骤
      snapshot: object,                        # [参数说明] 必填 原始快照
      trace_id: Optional[uuid.UUID] = None     # [参数说明] 可选
  ) -> CompensationPlan:                       # [返回值说明] 补偿计划
      """
      [函数职责] 构造补偿计划（已自动反转步骤顺序）
      
      Args:
          workspace_id: 工作空间 ID
          completed_steps: 已成功执行的步骤列表（按执行顺序）
          snapshot: 原始快照对象（用于最终恢复）
          trace_id: 追踪 ID
      
      Returns:
          CompensationPlan: 含反向步骤链
      """
[来源标注] [DD-M推断]
```

---

## API-280-5 SnapshotStep.forward

```
[接口编号] API-280-5
[关联契约] IC-012 (M-C05 list)
[实现文件] src/agenthub/infrastructure/acl_migration/steps/snapshot.py
[函数签名注释]
  async def forward(
      self,
      ctx: dict                              # [参数说明] 必填 ctx{workspace_id,trace_id}
  ) -> dict:                                 # [返回值说明] ctx 新增 snapshot/snapshot_hash
      """
      [函数职责] 创建 ACL 快照
      
      Args:
          ctx: 共享上下文
      
      Returns:
          更新后的 ctx（含 snapshot 与 snapshot_hash）
      
      Raises:
          MIGRATION_SNAPSHOT_FAILED: M-C05 list 失败
      """
[来源标注] [DD-001:IC-012] + [DD-001:MD-MCP-M-C09]
```

---

## API-280-6 ApplyStep.forward

```
[接口编号] API-280-6
[关联契约] IC-012 (M-C05 apply)
[实现文件] src/agenthub/infrastructure/acl_migration/steps/apply.py
[函数签名注释]
  async def forward(
      self,
      ctx: dict                              # [参数说明] 必填 ctx{workspace_id,rules,snapshot_hash}
  ) -> dict:                                 # [返回值说明] ctx 新增 applied_rule_ids
      """
      [函数职责] 应用新规则到 ACL 后端
      
      Args:
          ctx: 共享上下文
      
      Returns:
          更新后的 ctx（含 applied_rule_ids）
      
      Raises:
          MIGRATION_APPLY_FAILED: M-C05 apply 失败
          ACL_CONFLICT: 规则冲突（透传 M-C05）
      """
[来源标注] [DD-001:IC-012]
```

---

## API-280-7 ApplyStep.compensate

```
[接口编号] API-280-7
[关联契约] IC-012 (M-C05 revoke)
[实现文件] src/agenthub/infrastructure/acl_migration/steps/apply.py
[函数签名注释]
  async def compensate(
      self,
      ctx: dict                              # [参数说明] 必填 ctx{applied_rule_ids}
  ) -> None:                                 # [返回值说明] None
      """
      [函数职责] 撤销已应用的规则
      
      Args:
          ctx: 共享上下文
      
      Returns:
          None
      
      Raises:
          MIGRATION_REVOKE_FAILED: M-C05 revoke 失败
      """
[来源标注] [DD-001:IC-012]
```

---

## API-280-8 VerifyStep.forward

```
[接口编号] API-280-8
[关联契约] 无（内部探针）
[实现文件] src/agenthub/infrastructure/acl_migration/steps/verify.py
[函数签名注释]
  async def forward(
      self,
      ctx: dict                              # [参数说明] 必填 ctx{applied_rule_ids}
  ) -> dict:                                 # [返回值说明] ctx 新增 verify_result/probes
      """
      [函数职责] 探针验证新规则生效
      
      Args:
          ctx: 共享上下文
      
      Returns:
          更新后的 ctx（含 verify_result{probes_passed,probes_failed}）
      
      Raises:
          MIGRATION_VERIFY_FAILED: 任一探针不符
      """
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断]
```

---

## API-280-9 CommitStep.forward

```
[接口编号] API-280-9
[关联契约] IC-016 (history) / IC-020 (event)
[实现文件] src/agenthub/infrastructure/acl_migration/steps/commit.py
[函数签名注释]
  async def forward(
      self,
      ctx: dict                              # [参数说明] 必填 ctx{snapshot_hash,applied_rule_ids,verify_result}
  ) -> dict:                                 # [返回值说明] ctx 新增 history_id
      """
      [函数职责] 写入 mcp_migration_history（终态）
      
      Args:
          ctx: 共享上下文
      
      Returns:
          更新后的 ctx（含 history_id）
      
      Raises:
          MIGRATION_COMMIT_FAILED: PG 写入失败
      """
[来源标注] [DD-001:IC-016/IC-020]
```

---

## API-280-10 CommitStep.compensate（防御性）

```
[接口编号] API-280-10
[关联契约] IC-016
[实现文件] src/agenthub/infrastructure/acl_migration/steps/commit.py
[函数签名注释]
  async def compensate(
      self,
      ctx: dict                              # [参数说明] 必填
  ) -> None:                                 # [返回值说明] None
      """
      [函数职责] commit 不可补偿（防御性抛错）
      
      Raises:
          MIGRATION_NOT_COMPENSABLE: commit 已为终态
      """
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断]
```

---

**接口注释清单文档结束。**
