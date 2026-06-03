"""InboxDecision ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/inbox_decision.py
[文件职责] 映射 PG 表 inbox_decision（append-only 审批决策记录 + 哈希链）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-010 + DE-028 + SEC-005 + AR洞察-3 + DD洞察-5]
[功能描述]
  功能1: 定义 InboxDecision 类，继承 AppendOnlyMixin
  功能2: 字段 id / queue_id (UNIQUE FK) / decision / decision_hash (CHAR(64)) / prev_hash / custom_args (JSONB) / decider_id / decided_at / nonce
  功能3: 唯一索引 (queue_id, decision_hash) 实现幂等决策
  功能4: 哈希链字段 prev_hash → decision_hash 形成不可篡改链
[输入输出]
  输入: M-B04 ApprovalService.decide
  输出: 不可变决策审计记录
[依赖关系]
  依赖文件: ./base.py (AppendOnlyMixin)
  被依赖文件: ../repositories/inbox_decision.py
[注意事项]
  注意1: 严禁 UPDATE / DELETE，由 ORM event + PG trigger 双重防护（[DD洞察-5]）
  注意2: custom_args 通过 Vault Transit 加密后存储（DB 仅存密文）
  注意3: decision_hash = SHA256(prev_hash || queue_id || decision || decider_id || nonce || decided_at)，由应用层在 ApprovalService 计算
  注意4: 兼容 GDPR right to erasure 通过 redacted=true 标记字段实现（[DD洞察-5]），需在 DDR-MD01-001 评估添加
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2 + SEC-005]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-010 + SEC-005 + AR洞察-3 + DD洞察-5]
"""

# ============================================================
# [类名] InboxDecision
# [职责] 映射 inbox_decision 表（append-only + 哈希链审计）
# [属性]
#   id / queue_id (UNIQUE FK→inbox_queue) / decision (allow|deny) / decision_hash / prev_hash / custom_args (encrypted) / decider_id / decided_at / nonce
# [异常处理]
#   AppendOnlyViolation: 任意 UPDATE/DELETE 调用
#   IntegrityError: (queue_id, decision_hash) 重复 → 返回已有 decision_id（幂等）
# [来源标注] [DD-001:DS-010 + IC-006]
# ============================================================
