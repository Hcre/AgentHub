"""agenthub.infrastructure.dns_pinning 模块初始化.

[文件路径] src/agenthub/infrastructure/dns_pinning/__init__.py
[文件职责] DNS Pinning 模块公共接口导出
[所属模块] M-C04（DNS Pinning，来自 DD-001）
[关联设计规范] FS-013 / MD-MCP:M-C04 / IC-MCP:IC-011
[功能描述]
  功能1: 导出 Singleton 主类 DNSPinner，供 M-B05/M-C01 调用
  功能2: 导出 Redis 缓存代理 PinCache（Cache Proxy 模式）
  功能3: 导出领域异常类（DNSResolveError/BlacklistIPError/RedirectLoopError）
[输入输出]
  输入: 无（仅导出符号）
  输出: 公共接口符号
[依赖关系]
  依赖文件: ./pinner.py, ./cache.py, ./exceptions.py
  被依赖文件: M-B05 (MCP Create), M-C01 (Sandbox) - 通过 IC-011 调用
[注意事项]
  注意1: 本模块遵循 Singleton 模式，DNSPinner 实例全局唯一
  注意2: yarl.URL 对象必须保持单对象 Pin，跨模块传递时禁止重新构造 [TD:RSK-04]
  注意3: 缓存 TTL = 60s（短 TTL 是 DNS Rebinding 防御关键，[TD:S-032]）
[代码风格] 遵循 CS-MCP §1 Python 风格（PEP 484 类型注解 + Google Docstring）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C04 - 初始版本，导出公共接口
[作者] DD-M-C04-20260603
[来源标注] [DD-001:FS-013 + IC-MCP:IC-011]
"""

from agenthub.infrastructure.dns_pinning.cache import PinCache
from agenthub.infrastructure.dns_pinning.exceptions import (
    BlacklistIPError,
    CacheBackendError,
    DNSResolveError,
    RedirectLoopError,
)
from agenthub.infrastructure.dns_pinning.pinner import DNSPinner

__all__ = [
    "DNSPinner",
    "PinCache",
    "DNSResolveError",
    "BlacklistIPError",
    "RedirectLoopError",
    "CacheBackendError",
]
