"""IP 黑名单校验器.

[文件路径] src/agenthub/infrastructure/ssrf_guard/validators/ip_blacklist.py
[文件职责] 解析 host 为 IP 并查询 IPBlacklist
[所属模块] M-C06
[关联设计规范] MD-M-C06 / IC-013
[功能描述]
  功能1: 解析 url.host 为 IP（IPv4/IPv6）
  功能2: 命中黑名单（私网/loopback/云元数据）即 block
[依赖关系]
  依赖文件: ../blacklist.py
[代码风格] CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:MD-M-C06 + IC-013 + EX-004]
"""
from __future__ import annotations

import ipaddress

from yarl import URL

from agenthub.infrastructure.ssrf_guard.blacklist import IPBlacklist
from agenthub.infrastructure.ssrf_guard.validators.base import (
    CheckResult,
    URLValidator,
)


class IPBlacklistValidator(URLValidator):
    """IP 黑名单校验器（首层防御）.

    [类名] IPBlacklistValidator
    [职责] 解析 host 为 IP 并匹配黑名单
    [属性]
      属性1: _blacklist IPBlacklist 黑名单实例
    [来源标注] [DD-001:MD-M-C06 + EX-004]
    """
    layer: str = "ip_blacklist"

    def __init__(self, blacklist: IPBlacklist) -> None:
        """注入黑名单依赖.

        [函数名] __init__
        [职责] 初始化并注入 IPBlacklist
        [参数说明]
          参数1: blacklist IPBlacklist 必填
        [来源标注] [DD-001:MD-M-C06]
        """
        super().__init__()
        self._blacklist: IPBlacklist = blacklist

    def _do_validate(self, url: URL) -> CheckResult:
        """解析 host 为 IP 并查黑名单.

        [函数名] _do_validate
        [职责] 解析 → 查询 → 返回判定
        [参数说明]
          参数1: url yarl.URL 必填
        [返回值] CheckResult
        [错误码] ValueError: host 非 IP 字面量（由 DNSValidator 处理域名）
        [性能约束] < 5ms
        [来源标注] [DD-001:MD-M-C06 + IC-013]
        """
        raise NotImplementedError  # 占位
