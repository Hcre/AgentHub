"""test_redirect RedirectChecker 重定向重校验测试.

[文件路径] src/agenthub/infrastructure/dns_pinning/tests/test_redirect.py
[文件职责] RedirectChecker 重定向重校验测试（max 3 跳循环防护）
[所属模块] M-C04（DNS Pinning，来自 DD-001）
[关联设计规范] MD-MCP:M-C04 子模块 redirect/ + IC-MCP:IC-011
[测试策略]
  范围: 单元测试
  用例数: 3
  Mock: 无
  覆盖率: 行 ≥ 95%
[测试场景]
  场景1: 跳数 < 3 → 返回 True
  场景2: 跳数 == 3 → 抛 RedirectLoopError
  场景3: 跳数 > 3 → 抛 RedirectLoopError（边界外）
  场景4: max_hops 不可配置（参数化构造抛 ValueError）
[来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/ max 3 跳]
"""

from __future__ import annotations

import pytest
import yarl

from agenthub.infrastructure.dns_pinning.exceptions import RedirectLoopError
from agenthub.infrastructure.dns_pinning.redirect import RedirectChecker


# [测试场景1: 正常跳数]
@pytest.mark.asyncio
async def test_check_when_hops_less_than_max_then_return_true() -> None:
    """跳数 < 3: 正常返回 True.

    [断言] current_hops=2 时返回 True
    [Mock] 无
    [来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/]
    """
    checker = RedirectChecker()
    # 业务代码由 DD-S 实现后填充
    raise NotImplementedError("业务实现待 DD-S 完成后填充测试")


# [测试场景2: 跳数达上限]
@pytest.mark.asyncio
async def test_check_when_hops_equal_max_then_raise_loop_error() -> None:
    """跳数 == 3: 抛 RedirectLoopError.

    [断言] 抛出 RedirectLoopError；code = "REDIRECT_LOOP"
    [Mock] 无
    [来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/]
    """
    checker = RedirectChecker()
    with pytest.raises(RedirectLoopError):
        # 业务代码由 DD-S 实现后填充
        raise NotImplementedError("业务实现待 DD-S 完成后填充测试")


# [测试场景3: max_hops 不可配置]
def test_init_when_max_hops_not_3_then_raise_value_error() -> None:
    """max_hops 硬约束: != 3 抛 ValueError.

    [断言] RedirectChecker(max_hops=5) 抛 ValueError
    [Mock] 无
    [来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/ 安全硬约束]
    """
    with pytest.raises(ValueError, match="max_hops must be 3"):
        RedirectChecker(max_hops=5)
