# 接口注释清单 API-M-B05-MCP-V1.0-20260603

> M-B05 接口契约注释化清单 | 来源 [DD-001:IC-MCP/IC-007 + MD-MCP/M-B05]
> 涵盖 1 个跨进程 IC（IC-007）+ 5 个 in-proc Saga 步骤接口（IC-022 范畴）

---

## API-007 mcp.submit（IC-007 主体）

```
[接口编号] API-007
[关联契约] IC-MCP-V1.0-20260602 #IC-007
[实现文件] src/agenthub/application/create/controllers.py (CreateController.submit)
          + orchestrator.py (SagaOrchestrator.execute)
[函数签名注释]
  ```python
  async def submit(
      form: SubmitForm,  # [mcp_id/version/manifest_json/secrets 必填]
  ) -> SagaResult:        # [trace_id/status/steps_log]
      """
      [函数职责] MCP 提交入口；触发 5 步 Saga 链

      [关联接口契约] IC-007

      [参数说明]
        参数1: form SubmitForm 必填 含 mcp_id/version/manifest_json/secrets
                                  校验规则：version 匹配 semver；manifest 符合 JSON Schema 2020-12

      [返回值]
        类型: SagaResult
        描述: 包含 trace_id + status(queued|running|done|failed|rejected)
        特殊值: status=rejected 表示 K4/DryRun 失败（无补偿）

      [错误码]
        错误码1: MCP_DUPLICATE 409 UNIQUE(mcp_id, version) 冲突
        错误码2: MCP_K4_REJECTED 422 K4 判定 score ≥ 7
        错误码3: MCP_DRY_RUN_FAILED 422 dry_run 沙箱执行失败
        错误码4: MCP_SECRET_FAILED 500 Vault 写入失败（触发补偿）

      [前置条件] U-03 已认证；mcp_id 在白名单
      [后置条件] mcp_submission 表入库；事件 mcp.created/mcp.rollback_done 已发
      [并发安全] PG UNIQUE 约束；arq 单 trace_id 串行
      [幂等性]
        是否幂等: 是
        幂等键来源: (mcp_id, version)
        幂等有效期: 永久
        重复请求处理: 返回已有 trace_id
      [性能约束] P95 ≤ 5s（端到端）

      Example:
          >>> submit(SubmitForm(mcp_id=UUID(...), version="1.0.0", manifest_json={...}))
          SagaResult(trace_id=UUID(...), status="done", steps_log=[...])
      """
  ```
[来源标注] [DD-001:IC-MCP/IC-007]
```

---

## API-007-rollback 手动回滚

```
[接口编号] API-007-rollback
[关联契约] MD-MCP-V1.0-20260602 #M-B05
[实现文件] src/agenthub/application/create/controllers.py (CreateController.rollback)
[函数签名注释]
  ```python
  async def rollback(
      trace_id: UUID,         # [路径参数：Saga 链路追踪 ID]
      req: RollbackRequest,   # [请求体：reason + decider]
  ) -> SagaResult:             # [回滚结果]
      """
      [函数职责] 手动触发 Saga 补偿（运维入口）

      [参数说明]
        参数1: trace_id UUID 必填 Saga 链路 ID
        参数2: req RollbackRequest 必填 含 reason + decider

      [返回值] SagaResult status=failed

      [错误码]
        错误码1: ROLLBACK_NOT_FOUND 404 trace_id 不存在
        错误码2: ROLLBACK_PERMISSION_DENIED 403 decider 非 workspace admin
        错误码3: ROLLBACK_ALREADY_DONE 409 终态不可回滚

      [前置条件] decider ∈ workspace.admins
      [后置条件] compensator.run 触发；mcp.rollback_done 事件已发
      [并发安全] PG row-lock on mcp_submission
      [幂等性] 是；同 trace_id 重复 rollback 返回同结果
      [性能约束] P95 ≤ 1s
      """
  ```
[来源标注] [DD-001:MD-MCP/M-B05]
```

---

## API-Saga-005 Saga execute（in-proc 编排器入口）

```
[接口编号] API-Saga-005
[关联契约] IC-MCP-V1.0-20260602 #IC-022（in-proc 集合）
[实现文件] src/agenthub/application/create/orchestrator.py (SagaOrchestrator.execute)
[函数签名注释]
  ```python
  async def execute(
      trace_id: UUID,         # [链路追踪 ID]
      form: SubmitForm,       # [提交表单]
  ) -> SagaResult:             # [Saga 执行结果]
      """
      [函数职责] 串行执行 5 步 Saga 链

      [参数说明]
        参数1: trace_id UUID 必填 链路 ID（用于日志关联）
        参数2: form SubmitForm 必填 提交表单

      [返回值] SagaResult 含 status + steps_log

      [错误码]
        错误码1: DryRunFailed → 标 rejected（无补偿，[DDR-005]）
        错误码2: K4Failed → 标 rejected（不补偿，[DDR-005]）
        错误码3: SecretFailed → 补偿 metadata → 标 failed
        错误码4: MetadataFailed → 补偿 secret → 标 failed
        错误码5: HistoryFailed → 重试 max 3 → 标 done（仅告警）

      [前置条件] trace_id 已生成；mcp_submission 行已 INSERT（status=queued）
      [后置条件] 5 步全部完成；最终 status 写入 mcp_submission
      [并发安全] arq arity=1 串行（单 trace_id）
      [幂等性] 是；同 (mcp_id, version) 返回同 trace_id
      [性能约束] P95 ≤ 5s 端到端
      """
  ```
[来源标注] [DD-001:MD-MCP/M-B05 + DDR-005 + IC-MCP/IC-022]
```

---

## API-Step-001~005 5 个 Step 子类接口（in-proc）

每个 Step 子类继承 SagaStep 抽象基类，实现 forward(ctx) -> StepResult；其中 secret/metadata 额外实现 compensate(ctx) -> None。

| Step | forward 注释 | compensate 注释 | 来源 |
|------|------|------|------|
| DryRunStep | 沙箱预演；list[str] 必填；超时 30s | 默认 no-op（[DDR-005]） | [DD-001:MD-MCP/M-B05 + IC-MCP/IC-008] |
| K4Step | gRPC Analyze；score ≤ 3 pass / ≥ 7 reject | 默认 no-op（[DDR-005]） | [DD-001:MD-MCP/M-B05 + IC-MCP/IC-009] |
| SecretStep | VaultClient.put；vault_refs 入 ctx | 遍历 ctx.vault_refs 调用 VaultClient.delete | [DD-001:MD-MCP/M-B05 + IC-MCP/IC-014] |
| MetadataStep | UoW + 2 Repo（submission + server）写库 | UoW + SubmissionRepo.delete_by_trace | [DD-001:MD-MCP/M-B05 + IC-MCP/IC-017] |
| HistoryStep | UoW + HistoryRepo.append + EventBus.publish | 默认 no-op（业务已 done） | [DD-001:MD-MCP/M-B05 + DS-MCP/DS-013 + DDR-002] |

---

## 验收清单

| IC | 实现文件 | 函数签名 | 参数 | 返回值 | 错误码 | 验收 |
|----|---------|---------|------|--------|--------|------|
| IC-007 | controllers.py + orchestrator.py | ✓ | ✓ | ✓ | ✓ | 通过 |
| API-Saga-005 | orchestrator.py | ✓ | ✓ | ✓ | ✓ | 通过 |
| 5 Steps | steps/*.py | ✓ | ✓ | ✓ | ✓ | 通过 |

接口注释清单文档结束。
