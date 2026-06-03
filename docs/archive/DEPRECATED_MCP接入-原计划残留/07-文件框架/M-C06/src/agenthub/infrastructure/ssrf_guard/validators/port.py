"""Port 校验器（白名单 80/443）.

[文件路径] src/agenthub/infrastructure/ssrf_guard/validators/port.py
[文件职责] 拒绝非 80/443 端口
[所属模块] M-C06
[关联设计规范] MD-M-C06
[代码风格] CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:MD-M-C06 + IC-013]
"""
from __future__ import annotations

from yarl import URL

from agenthub.infrastructure.ssrf_guard.validators.base import (
    CheckResult,
    URLValidator,
)

ALLOWED_PORTS: frozenset[int] = frozenset({80, 443, 8080, 8443})


class PortValidator(URLValidator):
    """Port 白名单校验器.

    [类名] PortValidator
    [职责] 仅允许常用 web 端口
    [来源标注] [DD-001:MD-M-C06 + IC-013]
    """
    layer: str = "port"

    def _do_validate(self, url: URL) -> CheckResult:
        """校验端口在白名单.

        [函数名] _do_validate
        [职责] 端口白名单判定
        [参数说明]
          参数1: url yarl.URL 必填
        [返回值] CheckResult
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-C06]
        """
        raise NotImplementedError  # 占位
