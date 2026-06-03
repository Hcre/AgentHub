"""SSRF Chain 责任链入口.

[文件路径] src/agenthub/infrastructure/ssrf_guard/chain.py
[文件职责] 编排 5 层 SSRF 校验链，提供 check(url) 公共入口
[所属模块] M-C06（来自 DD-001）
[关联设计规范] FS-015 / MD-MCP-V1.0-20260602.md#M-C06 / IC-013
[功能描述]
  功能1: 顺序装配 Scheme→IPBlacklist→Port→Redirect→DNS 校验器
  功能2: 提供 sync/async 入口（< 50ms 性能约束）
  功能3: 触发 SSRFAttempt 时记录 url_hash + 拒绝层
[输入输出]
  输入: yarl.URL
  输出: CheckResult(pass/block + reason)
[依赖关系]
  依赖文件: ./validators/base.py, ./validators/{scheme,ip_blacklist,port,redirect,dns}.py
  被依赖文件: ./__init__.py, 上游 M-B05 / M-C02 / M-A03 调用方
[注意事项]
  注意1: 无状态；线程安全；可在多 worker 复用同一实例
  注意2: fail-secure: 任何 validator 抛异常即视为 block（[DD-001:EX-004]）
  注意3: 黑名单懒加载；首次 check 触发读取
[代码风格] 遵循 CS-001（来自 DD-001）
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:FS-015 + MD-M-C06 + IC-013 + EX-004]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from yarl import URL

from agenthub.infrastructure.ssrf_guard.validators.base import (
    CheckResult,
    URLValidator,
)

if TYPE_CHECKING:
    from agenthub.infrastructure.ssrf_guard.validators.dns import DNSValidator
    from agenthub.infrastructure.ssrf_guard.validators.ip_blacklist import (
        IPBlacklistValidator,
    )
    from agenthub.infrastructure.ssrf_guard.validators.port import PortValidator
    from agenthub.infrastructure.ssrf_guard.validators.redirect import (
        RedirectValidator,
    )
    from agenthub.infrastructure.ssrf_guard.validators.scheme import (
        SchemeValidator,
    )


class SSRFChain:
    """5 层 SSRF 防御链（Chain of Responsibility）.

    [类名] SSRFChain
    [职责] 顺序执行 5 个 URLValidator，返回首个拒绝/全通过
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-C06
    [属性]
      属性1: _head URLValidator 链头（type: URLValidator）
      属性2: _max_redirect_hop int 重定向最大跳数（type: int, default=3）
    [方法列表]
      方法1: check(url: yarl.URL) -> CheckResult - 同步入口（P95 < 50ms）
      方法2: build_default_chain() -> SSRFChain 类方法 - 装配 5 validator
    [状态机] 无（无状态）
    [异常处理]
      异常1: SSRFAttempt - 任何 validator 拒绝时上抛（带 url_hash + 拒绝层）
      异常2: SSRFCheckError - 校验器自身异常包装
    [并发安全] 线程安全（无共享可变状态）
    [来源标注] [DD-001:MD-M-C06 + IC-013]
    """

    def __init__(self, head: URLValidator, max_redirect_hop: int = 3) -> None:
        """初始化责任链.

        [函数名] __init__
        [职责] 注入链头与重定向上限
        [参数说明]
          参数1: head URLValidator 必填 链头
          参数2: max_redirect_hop int 可选 默认 3 重定向跳数
        [来源标注] [DD-001:MD-M-C06]
        """
        self._head: URLValidator = head
        self._max_redirect_hop: int = max_redirect_hop

    def check(self, url: URL) -> CheckResult:
        """SSRF 校验主入口（IC-013）.

        [函数名] check
        [职责] 顺序执行 5 层校验，返回 pass/block 结果
        [关联接口契约] IC-013 ssrf.check
        [参数说明]
          参数1: url yarl.URL 必填 待校验 URL
        [返回值]
          类型: CheckResult
          描述: pass=True 表示通过；pass=False 时 reason 字段填拒绝原因
        [错误码]
          SSRFAttempt: 拒绝时由调用方处理（[DD-001:EX-004]）
        [前置条件] url 非空且可被 yarl 解析
        [后置条件] 不修改 url；无副作用（除审计日志）
        [并发安全] 是
        [幂等性] 是（url → result；黑名单版本周期内）
        [性能约束] P95 < 50ms
        [来源标注] [DD-001:IC-013 + MD-M-C06]
        """
        return self._head.validate(url)

    @classmethod
    def build_default_chain(cls) -> "SSRFChain":
        """装配 5 validator 默认链.

        [函数名] build_default_chain
        [职责] 类工厂方法，返回装配好的 SSRFChain 实例
        [参数说明] 无
        [返回值] SSRFChain
        [来源标注] [DD-001:MD-M-C06 + FS-015]
        """
        raise NotImplementedError  # 占位：DD-S 阶段实现装配逻辑
