"""
[文件路径] src/agenthub/access/cron/tests/test_scheduler.py
[文件职责] CronScheduler 单元测试
[所属模块] M-A04（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602.md#M-A04 测试策略
[功能描述]
  功能1: 验证 load_jobs / start / shutdown 路径
  功能2: 验证 _on_trigger 回调派发
[输入输出] 输入: dispatcher/auditor mocks；输出: pytest 报告
[依赖关系]
  依赖文件: scheduler.py / dispatcher.py / auditor.py
  被依赖文件: 无
[注意事项] 注意1: APScheduler 真实实例或 stub
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-04 - 初始框架
[作者] DD-M-04-20260603
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 测试策略]
"""
from __future__ import annotations

import pytest

# [测试场景1: 加载 0 个 job]
# 输入: PG 返回空 cron_jobs
# 断言: load_jobs() 返回 0；scheduler 仍可 start
# Mock: asyncpg 查询 stub

# [测试场景2: 加载 1000 个 job]
# 输入: PG 返回 1000 行
# 断言: load_jobs() 返回 1000；耗时 ≤ 1s
# Mock: asyncpg fixture

# [测试场景3: _on_trigger 触发 dispatcher + auditor]
# 输入: 手动调用 _on_trigger("job-1", 1700000000)
# 断言: dispatcher.dispatch 被调用 1 次；auditor.on_trigger 被调用 1 次
# Mock: JobDispatcher spy + CronAuditor spy

# [测试场景4: shutdown wait=True 等待 running job]
# 输入: scheduler start 后调用 shutdown(wait=True)
# 断言: running job 完成后才返回
# Mock: APScheduler + running job fixture

# [测试场景5: 错开相位生效]
# 输入: phase_offset_sec=15；scheduler start
# 断言: trigger 时间包含 +15s 偏移
# Mock: APScheduler job queue
