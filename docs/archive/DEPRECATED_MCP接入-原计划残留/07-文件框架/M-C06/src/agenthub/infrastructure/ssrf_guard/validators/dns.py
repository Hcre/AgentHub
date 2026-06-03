"""DNS 校验器（与 M-C04 协同，Pinned IP 校验）.

[文件路径] src/agenthub/infrastructure/ssrf_guard/validators/dns.py
[文件职责] 跨模块调用 M-C04 DNSPinner 解析域名并阻断黑名单 IP
[所属模块] M-C06
[关联设计规范] MD-M-C06 / IC-011 / IC-013
[功能描述]
  功能1: 跨模块调用 M-C04 DNSPinner.resolve(url) 拿到 Pinned IP
  功能2: Pinned IP 命中黑名单 → block（防 DNS rebinding）
[依赖关系]
  依赖文件: [跨模块] M-C04 DNSPinner（IC-011）
  被依赖文件: ./scheme.py, ./port.py
[注意事项]
  注意1: 跨模块调用通过 IC-011，禁止直接 import 内部实现（TYPE_CHECKING）
  注意2: DNS 解析失败默认拒绝（fail-secure，[DD-001:EX-004]）
[代码风格] CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:MD-M-C06 + IC-011 + IC-013 + EX-004]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from yarl import URL

from agenthub.infrastructure.ssrf_guard.validators.base import (
    CheckResult,
    URLValidator,
)

if TYPE_CHECKING:
    from agenthub.infrastructure.dns_pinning.pinner import DNSPinner


class DNSValidator(URLValidator):
    """DNS 解析 + Pinned IP 黑名单校验器.

    [类名] DNSValidator
    [职责] 域名 → Pinned IP → 黑名单（防 DNS rebinding）
    [属性]
      属性1: _pinner DNSPinner [跨模块] 跨模块依赖 M-C04
    [来源标注] [DD-001:MD-M-C06 + IC-011 + EX-004]
    """
    layer: str = "dns"

    def __init__(self, pinner: "DNSPinner") -> None:
        """注入 M-C04 DNSPinner.

        [函数名] __init__
        [职责] 注入跨模块依赖
        [参数说明]
          参数1: pinner DNSPinner 必填 [跨模块] 来自 M-C04
        [来源标注] [DD-001:MD-M-C06 + IC-011]
        """
        super().__init__()
        self._pinner: "DNSPinner" = pinner

    def _do_validate(self, url: URL) -> CheckResult:
        """域名解析 + Pinned IP 黑名单查询.

        [函数名] _do_validate
        [职责] 解析域名 → 校验 Pinned IP
        [参数说明]
          参数1: url yarl.URL 必填
        [返回值] CheckResult
        [错误码] DNSResolveError → fail-secure block
        [性能约束] < 50ms（含 Redis 缓存命中）
        [来源标注] [DD-001:MD-M-C06 + IC-011]
        """
        raise NotImplementedError  # 占位
