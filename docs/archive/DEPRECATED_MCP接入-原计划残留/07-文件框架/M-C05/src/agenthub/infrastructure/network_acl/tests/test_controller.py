"""M-C05 controller 单元测试.

[文件路径] src/agenthub/infrastructure/network_acl/tests/test_controller.py
[文件职责] ACLController 与 IC-012 接口契约验证
[所属模块] M-C05（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C05
[测试策略]
  用例数: 9
  覆盖: 正常 apply / 幂等 / 冲突 / backend 切换 / revoke / 性能
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# [测试场景1: 正常 apply] [断言: 返回 applied_rule_ids 与 rules 长度一致] [Mock: backend.apply 成功]
# [测试场景2: 幂等 apply] [断言: 重复同 rule_hash 返回已存在 ID] [Mock: backend.apply 返回旧 IDs]
# [测试场景3: backend 不可用] [断言: 抛 ACLBackendUnavailable 503] [Mock: backend.healthcheck=False]
# [测试场景4: backend 降级] [断言: iptables 失败切到 ipset 成功] [Mock: iptables.fail / ipset.ok]
# [测试场景5: 规则冲突] [断言: 抛 ACLConflict 409] [Mock: backend.apply 抛 ConflictError]
# [测试场景6: revoke 存在规则] [断言: 200 + backend.revoke 调用 1 次] [Mock: repo.get 命中]
# [测试场景7: revoke 不存在规则] [断言: 404 ACL_NOT_FOUND] [Mock: repo.get 返回 None]
# [测试场景8: per-ws 串行] [断言: 同一 ws 并发 apply 最终不重叠] [Mock: 计数 backend.apply 调用次数]
# [测试场景9: 性能 P95≤1s] [断言: 100 rules apply < 1s] [Mock: backend 假延迟 5ms/rule]
