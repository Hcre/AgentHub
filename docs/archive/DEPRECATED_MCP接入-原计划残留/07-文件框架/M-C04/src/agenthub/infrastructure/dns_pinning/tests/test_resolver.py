"""test_resolver AsyncResolver aiodns 异步解析测试.

[文件路径] src/agenthub/infrastructure/dns_pinning/tests/test_resolver.py
[文件职责] AsyncResolver 异步解析测试（IPv4/IPv6/失败）
[所属模块] M-C04（DNS Pinning，来自 DD-001）
[关联设计规范] MD-MCP:M-C04 测试策略 / TS-019
[测试策略]
  范围: 单元测试
  用例数: 3
  Mock: aiodns.DNSResolver stub
  覆盖率: 行 ≥ 90%
[测试场景]
  场景1: 正常解析 IPv4（A 记录）
  场景2: 正常解析 IPv6（AAAA 记录）
  场景3: NXDOMAIN → 抛 DNSResolveError
  场景4: 超时 → 抛 DNSResolveError
[来源标注] [DD-001:MD-MCP:M-C04 子模块 resolver/ + TS-019]
"""

from __future__ import annotations

import pytest

from agenthub.infrastructure.dns_pinning.exceptions import DNSResolveError
from agenthub.infrastructure.dns_pinning.resolver import AsyncResolver


# [测试场景1: 正常解析 IPv4]
@pytest.mark.asyncio
async def test_resolve_hostname_when_ipv4_then_return_ipv4_list() -> None:
    """解析 IPv4: aiodns 返回 A 记录列表.

    [断言] result == ["93.184.216.34"]
    [Mock] aiodns.DNSResolver stub 返回 A 记录
    [来源标注] [DD-001:MD-MCP:M-C04 子模块 resolver/ + TS-019]
    """
    resolver = AsyncResolver()
    # 业务代码由 DD-S 实现后填充
    raise NotImplementedError("业务实现待 DD-S 完成后填充测试")


# [测试场景2: 正常解析 IPv6]
@pytest.mark.asyncio
async def test_resolve_hostname_when_ipv6_then_return_ipv6_list() -> None:
    """解析 IPv6: aiodns 返回 AAAA 记录列表.

    [断言] result == ["2606:2800:220:1:248:1893:25c8:1946"]
    [Mock] aiodns.DNSResolver stub 返回 AAAA 记录
    [来源标注] [DD-001:MD-MCP:M-C04 子模块 resolver/]
    """
    resolver = AsyncResolver()
    # 业务代码由 DD-S 实现后填充
    raise NotImplementedError("业务实现待 DD-S 完成后填充测试")


# [测试场景3: NXDOMAIN]
@pytest.mark.asyncio
async def test_resolve_hostname_when_nxdomain_then_raise_dns_error() -> None:
    """NXDOMAIN: 抛 DNSResolveError.

    [断言] 抛出 DNSResolveError
    [Mock] aiodns stub 抛 aiodns.error.DNSError
    [来源标注] [DD-001:MD-MCP:M-C04 异常处理 DNSResolveError]
    """
    resolver = AsyncResolver()
    with pytest.raises(DNSResolveError):
        # 业务代码由 DD-S 实现后填充
        raise NotImplementedError("业务实现待 DD-S 完成后填充测试")
