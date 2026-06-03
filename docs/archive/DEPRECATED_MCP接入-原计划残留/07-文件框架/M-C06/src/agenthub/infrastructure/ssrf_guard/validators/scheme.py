"""Scheme 校验器（白名单 http/https）.

[文件路径] src/agenthub/infrastructure/ssrf_guard/validators/scheme.py
[文件职责] 拒绝 file/ftp/gopher/javascript 等危险 scheme
[所属模块] M-C06
[关联设计规范] MD-M-C06 / IC-013
[功能描述] 白名单 scheme: http, https
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

ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class SchemeValidator(URLValidator):
    """Scheme 白名单校验器.

    [类名] SchemeValidator
    [职责] 仅允许 http/https；拒绝 file/ftp/gopher/javascript/data 等
    [来源标注] [DD-001:MD-M-C06 + IC-013]
    """
    layer: str = "scheme"

    def _do_validate(self, url: URL) -> CheckResult:
        """校验 url.scheme 是否在白名单.

        [函数名] _do_validate
        [职责] scheme 白名单判定
        [参数说明]
          参数1: url yarl.URL 必填
        [返回值] CheckResult
        [性能约束] O(1) 字符串匹配
        [来源标注] [DD-001:MD-M-C06]
        """
        raise NotImplementedError  # 占位
