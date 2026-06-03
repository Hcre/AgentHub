"""SSRF Guard 异常定义.

[文件路径] src/agenthub/infrastructure/ssrf_guard/exceptions.py
[文件职责] 定义 SSRF 校验相关异常类型
[所属模块] M-C06
[关联设计规范] EX-004（[DD-001]）
[功能描述]
  功能1: SSRFAttempt - 校验拒绝异常
  功能2: SSRFCheckError - 校验器内部异常
[输入输出]
  输入: 异常参数
  输出: 异常实例（含 url_hash + 拒绝层）
[依赖关系]
  依赖文件: agenthub.core.exceptions
  被依赖文件: ./chain.py, ./validators/*.py
[注意事项]
  注意1: 继承 agenthub.core.exceptions.SecurityError 以纳入统一响应格式
  注意2: 不在异常消息中暴露完整 URL（防日志泄露）
[代码风格] 遵循 CS-001
[创建日期] 2026-06-03
[作者] DD-M-15-20260603
[来源标注] [DD-001:EX-004 + SEC:SEC-004]
"""
from __future__ import annotations

from agenthub.core.exceptions import SecurityError


class SSRFAttempt(SecurityError):
    """SSRF 探测/拒绝异常（最高优先级，触发 CRITICAL 告警）.

    [类名] SSRFAttempt
    [职责] 表达 SSRF 校验链中的拒绝事件
    [属性]
      属性1: url_hash str SHA256(url)（脱敏）
      属性2: rejected_by str 拒绝层（scheme/ip_blacklist/port/redirect/dns）
      属性3: reason str 拒绝原因
    [来源标注] [DD-001:EX-004 + IC-013]
    """
    code: str = "SSRF_ATTEMPT"
    http_status: int = 403


class SSRFCheckError(SecurityError):
    """SSRF 校验器自身异常（fail-secure 触发 block）.

    [类名] SSRFCheckError
    [职责] 表达 validator 内部错误（与 SSRFAttempt 区分）
    [来源标注] [DD-001:EX-004]
    """
    code: str = "SSRF_CHECK_ERROR"
    http_status: int = 500
