"""SSRF IP 黑名单管理.

[文件路径] src/agenthub/infrastructure/ssrf_guard/blacklist.py
[文件职责] CIDR 黑名单加载与 O(1) 命中查询
[所属模块] M-C06
[关联设计规范] MD-MCP-V1.0-20260602.md#M-C06 / FS-015
[功能描述]
  功能1: 从 Vault/config 加载 CIDR 列表
  功能2: 提供 O(1) frozenset 命中（IPv4）/ 区间查询（IPv6）
  功能3: 支持热更新（reload）
[输入输出]
  输入: CIDR 列表（str）
  输出: bool（命中/未命中）
[依赖关系]
  依赖文件: 标准库 ipaddress
  被依赖文件: ./validators/ip_blacklist.py
[注意事项]
  注意1: 启动时懒加载；reload 期间使用旧版本不阻塞
  注意2: 包含 RFC1918 / loopback / link-local / 云元数据 169.254.169.254
  注意3: 内存常驻；CIDR 数 < 1万时可全内存
[代码风格] 遵循 CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:MD-M-C06 + FS-015 + SEC:SEC-004]
"""
from __future__ import annotations

import ipaddress
from typing import Final

from agenthub.core.logging import get_logger

log = get_logger(__name__)

# 常量: 预置高危 CIDR（与 [DD-001:EX-004] 配合）
DEFAULT_BLACKLIST_CIDRS: Final[tuple[str, ...]] = (
    "0.0.0.0/8",          # 本网络
    "10.0.0.0/8",         # RFC1918 私网
    "100.64.0.0/10",      # CGNAT
    "127.0.0.0/8",        # loopback
    "169.254.0.0/16",     # link-local + 云元数据
    "172.16.0.0/12",      # RFC1918 私网
    "192.0.0.0/24",       # IETF
    "192.168.0.0/16",     # RFC1918 私网
    "224.0.0.0/4",        # multicast
    "::1/128",            # IPv6 loopback
    "fc00::/7",           # IPv6 ULA
    "fe80::/10",          # IPv6 link-local
)


class IPBlacklist:
    """IP 黑名单管理器.

    [类名] IPBlacklist
    [职责] CIDR 集合的加载与命中查询
    [属性]
      属性1: _v4_nets tuple[ipaddress.IPv4Network, ...] IPv4 CIDR
      属性2: _v6_nets tuple[ipaddress.IPv6Network, ...] IPv6 CIDR
    [方法列表]
      方法1: contains(ip: str) -> bool - IP 命中判断
      方法2: load(cidrs: Sequence[str]) -> None - 重新加载
      方法3: reload_from_vault() -> None - 从 Vault 重载（热更新）
    [并发安全] 不可变 tuple；reload 时整体替换
    [来源标注] [DD-001:MD-M-C06]
    """

    def __init__(self, cidrs: tuple[str, ...] = DEFAULT_BLACKLIST_CIDRS) -> None:
        """初始化黑名单.

        [函数名] __init__
        [职责] 解析 CIDR 列表为 IPv4/IPv6 网络对象
        [参数说明]
          参数1: cidrs tuple[str, ...] 可选 默认 DEFAULT_BLACKLIST_CIDRS
        [错误码] ValueError: CIDR 格式非法
        [来源标注] [DD-001:MD-M-C06]
        """
        self._v4_nets: tuple[ipaddress.IPv4Network, ...] = ()
        self._v6_nets: tuple[ipaddress.IPv6Network, ...] = ()
        self.load(cidrs)

    def load(self, cidrs: tuple[str, ...]) -> None:
        """加载 CIDR 列表.

        [函数名] load
        [职责] 解析并分类 IPv4/IPv6 网络对象
        [参数说明]
          参数1: cidrs tuple[str, ...] 必填 CIDR 字符串元组
        [错误码] ValueError: 任一 CIDR 非法
        [幂等性] 是（重复 load 等价）
        [来源标注] [DD-M推断:基于 ipaddress 标准库]
        """
        raise NotImplementedError  # 占位：DD-S 阶段实现

    def contains(self, ip: str) -> bool:
        """判断 IP 是否在黑名单中.

        [函数名] contains
        [职责] O(1) 命中判断（IPv4 frozenset / IPv6 区间）
        [参数说明]
          参数1: ip str 必填 IPv4/IPv6 字串
        [返回值] bool True 命中
        [性能约束] O(N) 区间扫描；CIDR < 1万 时 < 1ms
        [来源标注] [DD-001:MD-M-C06]
        """
        raise NotImplementedError  # 占位

    def reload_from_vault(self) -> None:
        """从 Vault 热重载黑名单.

        [函数名] reload_from_vault
        [职责] 拉取最新 CIDR 列表并原子替换
        [并发安全] 整体替换；调用方在 reload 期间使用旧版
        [来源标注] [DD-M推断:热更新需求]
        """
        raise NotImplementedError  # 占位
