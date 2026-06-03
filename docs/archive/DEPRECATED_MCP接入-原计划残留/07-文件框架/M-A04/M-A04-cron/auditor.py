"""
[文件路径] src/agenthub/access/cron/auditor.py
[文件职责] Cron 触发审计；发布 trigger.cron.fired 事件
[所属模块] M-A04（来自DD-001）
[关联设计规范] FS-004 / MD-MCP-V1.0-20260602.md#M-A04 audit/ 子模块
[功能描述]
  功能1: 监听 cron 触发事件，发布到 Event Bus（M-EV01）
  功能2: 派发成功/失败均记录（INFO 成功 / ERROR 失败）
[输入输出]
  输入: job_name / ts（触发时间戳）
  输出: Event Bus trigger.cron.fired 事件
[依赖关系]
  依赖文件: M-EV01 eventbus / core.logging
  被依赖文件: scheduler.py（_on_trigger 调用）
[注意事项]
  注意1: 审计失败不影响主流程（best-effort）
  注意2: 事件 schema 遵循 M-EV01 topic registry trigger.cron.fired
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-04 - 初始框架
[作者] DD-M-04-20260603
[来源标注] [DD-001:FS-004 / MD-MCP-V1.0-20260602.md#M-A04 audit/ 子模块 + 类设计 CronAuditor]
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.eventbus.bus import EventBus

log = get_logger(__name__)


class CronAuditor:
    """[类名] CronAuditor
    [职责] 触发审计；发布 trigger.cron.fired 事件
    [关联设计规范] MD-MCP-V1.0-20260602.md#M-A04 类设计 CronAuditor
    [属性]
      属性1: bus EventBus  # Event Bus 客户端
    [方法列表]
      方法1: on_trigger(job_name, ts) → None  # 写审计 + 发布事件
    [状态机] 无
    [异常处理] 异常1: PublishError - 事件发布失败 → log.error + 不抛
    [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 类设计 CronAuditor]
    """

    TOPIC = "trigger.cron.fired"

    def __init__(self, bus: "EventBus") -> None:
        """[函数名] __init__
        [职责] 注入 Event Bus
        [参数说明] 参数1: bus EventBus 必填 事件总线
        [返回值] None
        [前置条件] EventBus 已初始化
        [后置条件] 可调用 on_trigger
        [并发安全] 构造线程安全
        [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 CronAuditor {bus}]
        """
        ...

    async def on_trigger(
        self,
        job_name: str,
        ts: int,
        dispatch_status: str = "success",
        error: str | None = None,
    ) -> None:
        """[函数名] on_trigger
        [职责] 记录 cron 触发 + 发布事件
        [参数说明]
          参数1: job_name str 必填 任务名
          参数2: ts int 必填 触发时间戳
          参数3: dispatch_status str 可选 默认 "success" [校验:enum[success|failed]]
          参数4: error str 可选 默认 None 失败原因
        [返回值] None
        [错误码] 无（审计失败仅 log）
        [前置条件] EventBus 健康
        [后置条件] 事件已发布（best-effort）
        [并发安全] 异步；多并发安全
        [幂等性] 否
        [性能约束] P95 ≤ 20ms
        [来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 函数签名 + audit 子模块]
        """
        ...
