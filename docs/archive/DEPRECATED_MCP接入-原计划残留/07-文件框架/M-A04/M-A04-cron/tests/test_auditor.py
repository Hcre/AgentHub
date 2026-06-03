"""
[文件路径] src/agenthub/access/cron/tests/test_auditor.py
[文件职责] CronAuditor 单元测试
[所属模块] M-A04（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602.md#M-A04 测试策略
[功能描述]
  功能1: 验证 on_trigger 写审计路径
  功能2: 验证 best-effort（bus 失败不抛）
[输入输出] 输入: EventBus spy；输出: pytest 报告
[依赖关系]
  依赖文件: auditor.py / agenthub.eventbus.bus.EventBus
  被依赖文件: 无
[注意事项] 注意1: 不依赖真实 Redis
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-04 - 初始框架
[作者] DD-M-04-20260603
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 测试策略 + audit 子模块]
"""
from __future__ import annotations

import pytest

# [测试场景1: 正常写审计]
# 输入: on_trigger("job-1", 1700000000)
# 断言: bus.publish 被调用 1 次，topic=trigger.cron.fired
# Mock: EventBus.publish spy

# [测试场景2: 派发失败写审计 + 错误信息]
# 输入: on_trigger("job-1", ts, dispatch_status="failed", error="arq down")
# 断言: payload 含 error 字段
# Mock: EventBus.publish spy

# [测试场景3: bus 异常不抛]
# 输入: bus.publish 抛 ConnectionError
# 断言: on_trigger 不抛异常（仅 log.error）
# Mock: EventBus.publish side_effect=ConnectionError
