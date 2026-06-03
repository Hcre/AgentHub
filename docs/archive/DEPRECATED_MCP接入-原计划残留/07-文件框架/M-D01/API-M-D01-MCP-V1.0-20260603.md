# API-M-D01-MCP-V1.0-20260603 接口注释清单

> [模块编号] M-D01 Metadata Store
> [关联契约] IC-017 metadata.dao（30 Repository 接口集）
> [关联 API] API-300

---

## 接口归属说明

M-D01 仅暴露 **in-proc Python 函数级接口**（IC-017 + IC-022 in-proc 类），不直接对外提供网络 API。所有 Repository 方法 100% 类型注解 + Google Docstring + raises 子句。

---

## API-300 / IC-017 metadata.dao — 接口注释清单

| 接口编号 | 实现文件 | 函数签名注释 | 参数说明 | 返回值说明 | 错误码说明 |
|----------|----------|--------------|----------|------------|------------|
| API-300.base.get | repositories/base.py::BaseRepository.get | 有 | 有 | 有 | DBUnavailable / DBIntegrityError |
| API-300.base.list | base.py::BaseRepository.list | 有 | 有 | 有 | DBUnavailable |
| API-300.base.list_by_spec | base.py::BaseRepository.list_by_spec | 有 | 有 | 有 | DBUnavailable |
| API-300.base.add | base.py::BaseRepository.add | 有 | 有 | 有 | DBIntegrityError / DBDeadlockExhausted |
| API-300.base.update | base.py::BaseRepository.update | 有 | 有 | 有 | AppendOnlyViolation / DBIntegrityError |
| API-300.base.delete | base.py::BaseRepository.delete | 有 | 有 | 有 | AppendOnlyViolation |
| API-300.base.select_for_update | base.py::BaseRepository.select_for_update | 有 | 有 | 有 | DBUnavailable |
| API-300.base.count | base.py::BaseRepository.count | 有 | 有 | 有 | DBUnavailable |
| API-300.uow.__aenter__ | unit_of_work.py::UnitOfWork.__aenter__ | 有 | 有 | 有 | DBUnavailable |
| API-300.uow.__aexit__ | unit_of_work.py::UnitOfWork.__aexit__ | 有 | 有 | 有 | RuntimeError（状态机违规） |
| API-300.uow.commit | unit_of_work.py::UnitOfWork.commit | 有 | 有 | 有 | DBIntegrityError |
| API-300.uow.rollback | unit_of_work.py::UnitOfWork.rollback | 有 | 有 | 有 | 无 |

| 域 Repository 方法（节选） | 实现文件 | 签名注释 | 参数 | 返回 | 错误码 |
|------|---------|---------|------|------|--------|
| MCPServerRepository.get_by_name | market_repos.py | 有 | 有 | 有 | DBUnavailable |
| MCPServerRepository.list_published | market_repos.py | 有 | 有 | 有 | DBUnavailable |
| MCPServerRepository.search | market_repos.py | 有 | 有 | 有 | DBUnavailable |
| MCPServerRepository.update_status | market_repos.py | 有 | 有 | 有 | InvalidStateTransition |
| ProcessPoolRepository.count_active_by_workspace | pool_repos.py | 有 | 有 | 有 | DBUnavailable |
| ProcessPoolRepository.lock_workspace_slot | pool_repos.py | 有 | 有 | 有 | DBLockTimeout |
| ProcessPoolRepository.transition_state | pool_repos.py | 有 | 有 | 有 | DBIntegrityError |
| HealthHistoryRepository.add_batch | pool_repos.py | 有 | 有 | 有 | DBIntegrityError |
| InboxQueueRepository.add_pending | approval_repos.py | 有 | 有 | 有 | DBIntegrityError（幂等返回） |
| InboxQueueRepository.lock_pending | approval_repos.py | 有 | 有 | 有 | DBLockTimeout / NotFoundInState |
| InboxQueueRepository.mark_decided | approval_repos.py | 有 | 有 | 有 | DBIntegrityError |
| InboxDecisionRepository.add | approval_repos.py | 有 | 有 | 有 | DBIntegrityError（幂等 hash 冲突） |
| InboxDecisionRepository.get_chain | approval_repos.py | 有 | 有 | 有 | DBUnavailable |
| Allowlist30dRepository.upsert | approval_repos.py | 有 | 有 | 有 | DBIntegrityError |
| Allowlist30dRepository.cleanup_expired | approval_repos.py | 有 | 有 | 有 | DBUnavailable |
| MCPSubmissionRepository.get_by_mcp_and_version | submission_repos.py | 有 | 有 | 有 | DBUnavailable |
| MCPSubmissionRepository.update_status | submission_repos.py | 有 | 有 | 有 | InvalidStateTransition |
| MCPSubmissionHistoryRepository.append | submission_repos.py | 有 | 有 | 有 | DBIntegrityError |
| WSSubscriptionRepository.list_by_topic | submission_repos.py | 有 | 有 | 有 | DBUnavailable |
| CronJobRepository.list_due | system_repos.py | 有 | 有 | 有 | DBUnavailable |
| K4RuleSetRepository.activate | system_repos.py | 有 | 有 | 有 | DBIntegrityError |
| ACLRuleRepository.add_idempotent | system_repos.py | 有 | 有 | 有 | DBIntegrityError（幂等 hash） |
| SecretRefRepository.list_due_rotation | system_repos.py | 有 | 有 | 有 | DBUnavailable |
| MCPMigrationHistoryRepository.append | system_repos.py | 有 | 有 | 有 | DBIntegrityError |

---

## 接口契约注释化覆盖率

| IC | 关联模块外接口（被 IC-017 覆盖） | 注释体现 |
|----|----------------------------------|----------|
| IC-004 pool.spawn | 由 ProcessPoolRepository.lock_workspace_slot / transition_state / count_active 协助 | ✓ |
| IC-005 approval.check_and_queue | InboxQueueRepository.add_pending / Allowlist30dRepository.is_allowed | ✓ |
| IC-006 approval.decide | InboxQueueRepository.lock_pending / InboxDecisionRepository.add / Allowlist30dRepository.upsert | ✓ |
| IC-007 mcp.submit | MCPSubmissionRepository.add / get_by_mcp_and_version / MCPSubmissionHistoryRepository.append | ✓ |
| IC-009 K4.Analyze | K4RuleSetRepository.get_active（被 M-C02 调用） | ✓ |
| IC-012 acl.apply | ACLRuleRepository.add_idempotent（rule_hash 幂等） | ✓ |
| IC-016 acl.migrate | MCPMigrationHistoryRepository.append（append-only） | ✓ |
| IC-017 metadata.dao | UnitOfWork + BaseRepository + 17 Repo | ✓ |

**D4 接口契约注释化完整度 = 100%（8/8 关联 IC 全部体现）**

---

## 函数签名 Docstring 示例（base.py::add）

```python
async def add(self, entity: T) -> UUID:
    """插入新实体并返回主键.

    Args:
        entity: ORM 实例（必须是 self._model_class 类型；UUID 主键留空由 PG 默认生成）

    Returns:
        新行主键 UUID

    Raises:
        DBIntegrityError: 唯一约束 / 外键 / CHECK 违反
        DBDeadlockExhausted: 重试 3 次仍 PG SQLSTATE 40P01
        DBUnavailable: 连接池耗尽或 PG 不可达
        AppendOnlyViolation: 子类覆盖禁用 add（一般无此情况）

    Example:
        >>> async with UnitOfWork(engine) as uow:
        ...     mcp = MCPServer(name="foo", version="1.0.0", ...)
        ...     mcp_id = await uow.mcp_servers.add(mcp)
    """
```

---

**[来源标注]** [DD-001:IC-017 + IC-004/005/006/007/009/012/016 + MD:M-D01]

**接口注释清单文档结束。**
