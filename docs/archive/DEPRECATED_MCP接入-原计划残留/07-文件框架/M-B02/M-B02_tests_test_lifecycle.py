"""M-B02 ProcessStateMachine 单元测试.

[文件路径] src/agenthub/application/pool/tests/test_lifecycle.py
[文件职责] 状态机转换测试
[所属模块] M-B02
[关联设计规范] FS-006 / MD-MCP-V1.0-20260602
[测试策略]
  范围: 单元
  用例数: 12（5 业务状态 × 主转换 + 异常路径）
  Mock: 无（纯逻辑）
  覆盖率: 行 ≥ 90%

测试场景:
  - test_transition_when_spawn_requested_from_idle_then_spawn_requested
      断言: state 从 IDLE 经 spawn_requested 事件 → SPAWN_REQUESTED
  - test_transition_when_spawn_ok_from_spawning_then_running
      断言: SPAWNING → RUNNING
  - test_transition_when_spawn_fail_from_spawning_then_reserved
      断言: SPAWNING → SPAWN_REQUESTED（重试）
  - test_transition_when_idle_5min_from_running_then_idle
      断言: RUNNING → IDLE
  - test_transition_when_health_fail_3_times_then_zombie
      断言: RUNNING → ZOMBIE（连续 3 次）
  - test_transition_when_recycle_from_zombie_then_recycling
      断言: ZOMBIE → RECYCLING
  - test_transition_when_invalid_event_then_raise_value_error
      断言: 非法事件 → ValueError
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7 测试规范
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:FS-006 + MD-MCP-M-B02]
"""
from __future__ import annotations

import pytest
from uuid import uuid4

# 业务测试由开发工程师实现；此处声明场景注释
__all__: list[str] = []
