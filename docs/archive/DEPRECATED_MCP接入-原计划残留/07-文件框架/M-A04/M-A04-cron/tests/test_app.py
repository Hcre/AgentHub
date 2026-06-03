"""
[文件路径] src/agenthub/access/cron/tests/test_app.py
[文件职责] CronApp 集成测试（多实例 + leader 切换）
[所属模块] M-A04（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602.md#M-A04 测试策略（用例数 15）
[功能描述]
  功能1: 验证 start/stop 完整生命周期
  功能2: 验证多实例 leader 切换
[输入输出] 输入: 真实/fakeredis + 真实 scheduler；输出: pytest 报告
[依赖关系]
  依赖文件: app.py / scheduler.py / leader_elector.py / dispatcher.py / auditor.py
  被依赖文件: 无
[注意事项] 注意1: 多实例测试需 asyncio.gather 启动 2 个 CronApp
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-04 - 初始框架
[作者] DD-M-04-20260603
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 测试策略]
"""
from __future__ import annotations

import pytest

# [测试场景1: 单实例 start 抢到 leader]
# 输入: 1 个 CronApp.start()
# 断言: leader.is_leader=True；scheduler.running=True
# Mock: fakeredis + 真实 scheduler

# [测试场景2: 两实例 start 仅 1 个抢到 leader]
# 输入: 2 个 CronApp.start() 并发
# 断言: 1 个 is_leader=True，1 个 False
# Mock: fakeredis + asyncio.gather

# [测试场景3: leader 失联后让位]
# 输入: leader 实例 stop()；另一实例 acquire
# 断言: 新实例 30s 内成为 leader
# Mock: fakeredis + 时间桩

# [测试场景4: stop 优雅停机]
# 输入: CronApp.stop()
# 断言: scheduler 关闭；Redis 锁释放；进程退出 ≤ 30s
# Mock: 无

# [测试场景5: healthz 始终返回 ok]
# 输入: healthz() 调用
# 断言: {"status": "ok", "module": "M-A04", "state": "Leader|Standby"}
# Mock: 无

# [测试场景6: readyz 仅 Leader=True]
# 输入: Standby 实例 readyz()
# 断言: False
# Mock: 无
