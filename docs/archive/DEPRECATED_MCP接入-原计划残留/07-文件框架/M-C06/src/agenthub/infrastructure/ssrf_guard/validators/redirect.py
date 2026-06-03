"""Redirect 校验器（重定向链二次校验）.

[文件路径] src/agenthub/infrastructure/ssrf_guard/validators/redirect.py
[文件职责] 防止 DNS rebinding 攻击，重定向时重新走 5 层校验
[所属模块] M-C06
[关联设计规范] MD-M-C06 / IC-013
[功能描述]
  功能1: 拦截 30x 重定向，对 Location 头指向的 URL 重新走链
  功能2: 限制最大跳数（默认 3）防无限循环
[依赖关系]
  依赖文件: ../chain.py（[DD-001:跨模块依赖 M-C04 仅 DNS Pinning，本模块仅 self-loop]）
[代码风格] CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:MD-M-C06 + IC-013 + ADR-004]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from yarl import URL

from agenthub.infrastructure.ssrf_guard.validators.base import (
    CheckResult,
    URLValidator,
)

if TYPE_CHECKING:
    from agenthub.infrastructure.ssrf_guard.chain import SSRFChain


class RedirectValidator(URLValidator):
    """重定向二次校验器.

    [类名] RedirectValidator
    [职责] 拦截 30x 响应，对 Location 重新走 SSRFChain
    [属性]
      属性1: _chain_ref SSRFChain 弱引用避免循环导入
      属性2: _max_hop int 最大跳数（默认 3）
    [来源标注] [DD-001:MD-M-C06 + ADR-004]
    """
    layer: str = "redirect"

    def __init__(self, max_hop: int = 3) -> None:
        """初始化跳数上限.

        [函数名] __init__
        [职责] 设置最大跳数
        [参数说明]
          参数1: max_hop int 可选 默认 3
        [来源标注] [DD-001:MD-M-C06]
        """
        super().__init__()
        self._max_hop: int = max_hop

    def _do_validate(self, url: URL) -> CheckResult:
        """解析重定向并递归校验.

        [函数名] _do_validate
        [职责] 跟踪 Location 头并复用 SSRFChain
        [参数说明]
          参数1: url yarl.URL 必填 原始 URL
        [返回值] CheckResult
        [性能约束] 总耗时 < 50ms（含最多 3 跳）
        [来源标注] [DD-001:MD-M-C06 + ADR-004]
        """
        raise NotImplementedError  # 占位
