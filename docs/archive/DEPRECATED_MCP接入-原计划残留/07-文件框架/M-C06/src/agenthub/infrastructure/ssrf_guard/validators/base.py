"""URL Validator 抽象基类.

[文件路径] src/agenthub/infrastructure/ssrf_guard/validators/base.py
[文件职责] 定义 URLValidator ABC + set_next 链式接口 + CheckResult
[所属模块] M-C06
[关联设计规范] MD-MCP-V1.0-20260602.md#M-C06
[功能描述]
  功能1: 抽象基类，定义 validate(url) -> CheckResult 接口
  功能2: 链式装配 set_next(next: URLValidator) -> URLValidator
  功能3: CheckResult 不可变数据类（pass/block + reason）
[输入输出]
  输入: yarl.URL
  输出: CheckResult
[依赖关系]
  依赖文件: pydantic（BaseModel） / yarl
  被依赖文件: ./scheme.py, ./ip_blacklist.py, ./port.py, ./redirect.py, ./dns.py
[注意事项]
  注意1: 链式短路——一旦某层 block，后续 validator 不再执行
  注意2: fail-secure——validator 内部异常应转为 block（不在此基类实现，由各子类决定）
[代码风格] 遵循 CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:MD-M-C06 + IC-013]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from yarl import URL


@dataclass(frozen=True)
class CheckResult:
    """校验结果（不可变）.

    [类名] CheckResult
    [职责] 表达单层 validator 的判定结果
    [属性]
      属性1: pass bool True 通过 / False 拒绝
      属性2: reason str 拒绝原因（pass=True 时为空）
      属性3: layer str 校验层名（用于审计）
    [来源标注] [DD-001:IC-013 + MD-M-C06]
    """
    pass_: bool
    reason: str
    layer: str


class URLValidator(ABC):
    """URL 校验器抽象基类（Chain of Responsibility 节点）.

    [类名] URLValidator
    [职责] 定义链式校验器接口
    [属性]
      属性1: _next URLValidator | None 后继节点
    [方法列表]
      方法1: set_next(next: URLValidator) -> URLValidator - 装配后继（流畅接口）
      方法2: validate(url: yarl.URL) -> CheckResult - 模板方法（先本层后 next）
      方法3: _do_validate(url: yarl.URL) -> CheckResult - 抽象方法（子类实现）
    [状态机] 无
    [异常处理] 子类 _do_validate 抛 SSRFAttempt / SSRFCheckError
    [并发安全] 是
    [来源标注] [DD-001:MD-M-C06]
    """
    def __init__(self) -> None:
        self._next: URLValidator | None = None

    def set_next(self, next_validator: "URLValidator") -> "URLValidator":
        """设置后继 validator（流畅接口）.

        [函数名] set_next
        [职责] 装配后继节点并返回自身
        [参数说明]
          参数1: next_validator URLValidator 必填 后继
        [返回值] URLValidator 自身（支持链式调用）
        [来源标注] [DD-001:MD-M-C06]
        """
        self._next = next_validator
        return self

    def validate(self, url: URL) -> CheckResult:
        """模板方法：先本层校验，通过则委派后继.

        [函数名] validate
        [职责] Chain of Responsibility 模板方法
        [参数说明]
          参数1: url yarl.URL 必填
        [返回值] CheckResult
        [并发安全] 是
        [幂等性] 是
        [来源标注] [DD-001:MD-M-C06]
        """
        result: CheckResult = self._do_validate(url)
        if not result.pass_:
            return result
        if self._next is None:
            return result
        return self._next.validate(url)

    @abstractmethod
    def _do_validate(self, url: URL) -> CheckResult:
        """子类实现具体校验逻辑.

        [函数名] _do_validate
        [职责] 单层校验逻辑
        [参数说明]
          参数1: url yarl.URL 必填
        [返回值] CheckResult
        [来源标注] [DD-001:MD-M-C06]
        """
        raise NotImplementedError  # 占位
