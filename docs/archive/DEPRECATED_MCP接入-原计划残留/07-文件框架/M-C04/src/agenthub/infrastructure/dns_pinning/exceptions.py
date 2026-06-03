"""agenthub.infrastructure.dns_pinning.exceptions DNS 领域异常定义.

[文件路径] src/agenthub/infrastructure/dns_pinning/exceptions.py
[文件职责] DNS 领域异常基类 + 4 个具体异常
[所属模块] M-C04（DNS Pinning，来自 DD-001）
[关联设计规范] FS-013 / MD-MCP:M-C04 异常处理 / CS-MCP §1.6 异常处理规范
[功能描述]
  功能1: 定义 DNS 解析、缓存、黑名单、重定向异常
  功能2: 继承 agenthub.core.exceptions.AgentHubError 基类
  功能3: 异常链通过 raise X from e 保留（[CS-001 §1.6]）
[输入输出] 无（仅定义异常类）
[依赖关系]
  依赖文件:
    - agenthub.core.exceptions.AgentHubError [DD-M推断:跨模块基类]
  被依赖文件:
    - ./pinner.py, ./cache.py, ./resolver.py, ./blacklist.py, ./redirect.py
    - M-B05 (MCP Create) 捕获并转换为业务错误码
[注意事项]
  注意1: 所有异常必须继承 AgentHubError，统一异常处理
  注意2: 错误码字段便于日志结构化采集
  注意3: 异常消息必须包含上下文（host/ip/url_hash）便于排障
[代码风格] 遵循 CS-MCP §1 Python 风格
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C04 - 初始版本
[作者] DD-M-C04-20260603
[来源标注] [DD-001:MD-MCP:M-C04 异常处理 + CS-MCP §1.6]
"""

from __future__ import annotations

from agenthub.core.exceptions import AgentHubError


class DNSResolveError(AgentHubError):
    """DNS 解析失败异常.

    [类名] DNSResolveError
    [职责] aiodns 解析失败（NXDOMAIN/timeout/网络异常）时抛出
    [关联设计规范] MD-MCP:M-C04 异常处理 / CS-MCP §1.6
    [属性]
      属性1: host str - 解析失败的域名
      属性2: cause str - 底层异常描述
    [方法列表] 无新增方法（继承 AgentHubError）
    [状态机] 无
    [异常处理]
      触发条件: NXDOMAIN / timeout / 网络不可达
    [来源标注] [DD-001:MD-MCP:M-C04 异常处理]
    """

    code: str = "DNS_RESOLVE_FAILED"
    http_status: int = 502

    def __init__(self, host: str, cause: str = "") -> None:
        """DNSResolveError 初始化.

        [函数名] __init__
        [职责] 构造异常，附加 host 与 cause
        [参数说明]
          参数1: host str 必填 失败域名
          参数2: cause str 可选 底层原因描述
        [返回值] None
        [来源标注] [DD-001:MD-MCP:M-C04]
        """
        super().__init__(f"DNS resolve failed for host={host!r}: {cause}")
        self.host: str = host
        self.cause: str = cause


class BlacklistIPError(AgentHubError):
    """黑名单 IP 命中异常.

    [类名] BlacklistIPError
    [职责] 解析结果 IP 在黑名单 CIDR 段时抛出（[MD-004 异常处理]）
    [关联设计规范] MD-MCP:M-C04 异常处理 / IC-MCP:IC-011
    [属性]
      属性1: ip str - 命中的 IP
      属性2: host str - 原始域名
      属性3: cidr str - 命中的 CIDR 段
    [方法列表] 无新增方法
    [状态机] 无
    [异常处理]
      触发条件: IP 落在 IPBlacklist 任一 CIDR 段
    [来源标注] [DD-001:MD-MCP:M-C04 异常处理 BlacklistIPError + IC-MCP:IC-011]
    """

    code: str = "BLACKLIST_IP"
    http_status: int = 403

    def __init__(self, ip: str, host: str, cidr: str) -> None:
        """BlacklistIPError 初始化.

        [函数名] __init__
        [职责] 构造异常，附加 IP/host/CIDR
        [参数说明]
          参数1: ip str 必填 命中 IP
          参数2: host str 必填 原始域名
          参数3: cidr str 必填 命中 CIDR
        [返回值] None
        [来源标注] [DD-001:MD-MCP:M-C04 + IC-MCP:IC-011]
        """
        super().__init__(f"IP {ip!r} for host={host!r} is in blacklist CIDR={cidr!r}")
        self.ip: str = ip
        self.host: str = host
        self.cidr: str = cidr


class RedirectLoopError(AgentHubError):
    """重定向循环异常.

    [类名] RedirectLoopError
    [职责] 重定向跳数 > max_hops=3 时抛出
    [关联设计规范] MD-MCP:M-C04 子模块 redirect/
    [属性]
      属性1: hops int - 实际跳数
      属性2: max_hops int - 上限
      属性3: chain list[str] - 重定向链（域名列表）
    [方法列表] 无新增方法
    [状态机] 无
    [异常处理]
      触发条件: hops > max_hops
    [来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/]
    """

    code: str = "REDIRECT_LOOP"
    http_status: int = 508

    def __init__(self, hops: int, max_hops: int, chain: list[str]) -> None:
        """RedirectLoopError 初始化.

        [函数名] __init__
        [职责] 构造异常，附加跳数与链路
        [参数说明]
          参数1: hops int 必填 实际跳数
          参数2: max_hops int 必填 上限
          参数3: chain list[str] 必填 链路域名
        [返回值] None
        [来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/]
        """
        super().__init__(f"Redirect loop detected: hops={hops} > max_hops={max_hops}, chain={chain}")
        self.hops: int = hops
        self.max_hops: int = max_hops
        self.chain: list[str] = chain


class CacheBackendError(AgentHubError):
    """Redis 缓存后端异常.

    [类名] CacheBackendError
    [职责] Redis 集群不可用/超时时抛出
    [关联设计规范] MD-MCP:M-C04 子模块 cache/ / CS-MCP §1.6 异常转译
    [属性]
      属性1: operation str - 失败操作 (get/set/delete)
      属性2: cause str - 底层异常
    [方法列表] 无新增方法
    [状态机] 无
    [异常处理]
      触发条件: redis.exceptions.ConnectionError/TimeoutError
    [来源标注] [DD-M推断:依据 MD-004 子模块 cache/ + CS-001 §1.6 异常转译]
    """

    code: str = "CACHE_BACKEND_ERROR"
    http_status: int = 503

    def __init__(self, operation: str, cause: str = "") -> None:
        """CacheBackendError 初始化.

        [函数名] __init__
        [职责] 构造异常，附加 operation 与 cause
        [参数说明]
          参数1: operation str 必填 失败操作
          参数2: cause str 可选 底层原因
        [返回值] None
        [来源标注] [DD-M推断:依据 MD-004 子模块 cache/ + CS-001]
        """
        super().__init__(f"Redis cache {operation!r} failed: {cause}")
        self.operation: str = operation
        self.cause: str = cause
