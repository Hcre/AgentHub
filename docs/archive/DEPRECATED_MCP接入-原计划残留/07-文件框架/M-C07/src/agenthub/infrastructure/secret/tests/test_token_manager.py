"""TokenManager 测试.

[文件路径] src/agenthub/infrastructure/secret/tests/test_token_manager.py
[文件职责] 覆盖 token 获取、续期、过期重建
[所属模块] M-C07
[关联设计规范] FS-016 / MD-M-C07 / IC-014 / CS-MCP-V1.0 §1.7
[测试策略]
  范围: 单元
  用例数: 5
  覆盖率目标: 行 ≥ 90%
  Mock 策略: 时间快进（freezegun / asyncio.sleep mock）
[来源标注] [DD-001:MD-M-C07/IC-014 + CS-MCP-V1.0 §1.7]
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------
# 测试场景清单
# ----------------------------------------------------------------------
# 1. test_start_when_first_call_then_get_dynamic_token
#    断言: _current_token 非空；renew_task 已创建
#    Mock: httpx POST /auth/token/create
#
# 2. test_get_dynamic_token_when_ttl_left_then_return_cached
#    断言: 第二次调用 httpx 仅被调用一次
#    Mock: time.monotonic 控制
#
# 3. test_get_dynamic_token_when_near_expiry_then_renew_blocking
#    断言: 内部调用 renew；返回新 token
#    Mock: freezegun
#
# 4. test_renew_when_vault_5xx_then_retry_3_times
#    断言: 最终抛出 VaultSealed
#    Mock: httpx 返回 500 三次
#
# 5. test_stop_when_called_then_cancel_task_and_clear_token
#    断言: renew_task 状态 cancelled；_current_token 为 None
#    Mock: 无
