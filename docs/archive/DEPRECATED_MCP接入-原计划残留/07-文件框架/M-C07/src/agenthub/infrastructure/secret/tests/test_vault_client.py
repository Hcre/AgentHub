"""VaultClient 测试.

[文件路径] src/agenthub/infrastructure/secret/tests/test_vault_client.py
[文件职责] 覆盖 VaultClient 4 个公开方法 + 健康探测
[所属模块] M-C07
[关联设计规范] FS-016 / MD-M-C07 / IC-014 / CS-MCP-V1.0 §1.7
[测试策略]
  范围: 单元（Mock httpx + fakeredis-like）
  用例数: 6
  覆盖率目标: 行 ≥ 90%
  Mock 策略: pytest-mock / httpx.MockTransport
[来源标注] [DD-001:MD-M-C07/IC-014 + CS-MCP-V1.0 §1.7]
"""

from __future__ import annotations

import pytest

# 占位：实际测试由 Dev 阶段实现
pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------
# 测试场景清单
# ----------------------------------------------------------------------
# 1. test_get_when_cache_miss_then_call_vault_and_cache
#    断言: 第二次 get 命中缓存，httpx 仅被调用一次
#    Mock: SecretCache.get 返回 None；httpx 返回 secret/data
#
# 2. test_get_when_cache_hit_then_skip_vault
#    断言: 仅一次 HTTP 调用
#    Mock: SecretCache.get 返回 bytes
#
# 3. test_put_when_success_then_invalidate_cache
#    断言: SecretCache.invalidate 被调用一次
#    Mock: httpx.put 返回 204
#
# 4. test_encrypt_when_vault_429_then_raise
#    断言: 抛出 VaultRateLimited
#    Mock: httpx 返回 429
#
# 5. test_health_when_vault_sealed_then_raise_and_block_startup
#    断言: 抛出 VaultSealed
#    Mock: httpx 返回 503 sealed
#
# 6. test_aclose_when_called_twice_then_idempotent
#    断言: 第二次不报错
#    Mock: httpx.AsyncClient.aclose
