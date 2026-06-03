"""Transit 测试.

[文件路径] src/agenthub/infrastructure/secret/tests/test_transit.py
[文件职责] 覆盖 encrypt/decrypt/rotate 三个公开方法
[所属模块] M-C07
[关联设计规范] FS-016 / MD-M-C07 / IC-014 / CS-MCP-V1.0 §1.7
[测试策略]
  范围: 单元
  用例数: 4
  覆盖率目标: 行 ≥ 90%
  Mock 策略: httpx MockTransport
[来源标注] [DD-001:MD-M-C07/IC-014 + CS-MCP-V1.0 §1.7]
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------
# 测试场景清单
# ----------------------------------------------------------------------
# 1. test_encrypt_when_success_then_return_vault_v1_format
#    断言: 输出以 "vault:v1:" 开头
#    Mock: httpx 返回 vault 标准 ciphertext
#
# 2. test_decrypt_when_ciphertext_invalid_then_raise
#    断言: 抛出 VaultInvalidCiphertext
#    Mock: httpx 返回 400
#
# 3. test_encrypt_when_payload_too_large_then_raise
#    断言: 抛出 VaultInvalidPlaintext
#    Mock: httpx 返回 413
#
# 4. test_rotate_key_when_no_permission_then_raise
#    断言: 抛出 VaultPermissionDenied
#    Mock: httpx 返回 403
