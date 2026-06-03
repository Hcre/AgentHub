"""M-A03 Webhook Receiver 异常定义.

[文件路径] src/agenthub/access/webhook/exceptions.py
[文件职责] 集中定义 Webhook 接收链路的领域异常类型
[所属模块] M-A03（来自DD-001）
[关联设计规范] MD-M-A03 / IC-003（来自DD-001）
[功能描述]
  功能1: 定义 WebhookError 基类（继承 agenthub.core.exceptions.AgentHubError）
  功能2: 定义验签失败异常 HMACMismatchError（→ 401 WEBHOOK_HMAC_FAILED）
  功能3: 定义重放检测异常 ReplayDetected（→ 409 WEBHOOK_REPLAY）
  功能4: 定义入队失败异常 EnqueueError（→ 503, 重试 max 3）
[输入输出]
  输入: 异常构造参数（错误码、源系统、payload 摘要）
  输出: 标准 AgentHubError 子类
[依赖关系]
  依赖文件: agenthub.core.exceptions.AgentHubError
  被依赖文件: app.py / verifiers/*.py / replay_guard.py / enqueuer.py
[注意事项]
  注意1: 异常类须提供 status_code 与 error_code 字段，供 controllers 直接序列化
  注意2: HMACMismatchError 必须携带 signature_valid=False 标记，供 metrics 打点
  注意3: 不在异常中携带 secret 原文
[代码风格] 遵循CS-MCP-V1.0 §1.6（异常处理规范）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本
[作者] DD-M-A03-20260603
[来源标注] [DD-001:MD-M-A03 + IC-003]
"""

from __future__ import annotations

from agenthub.core.exceptions import AgentHubError


class WebhookError(AgentHubError):
    """Webhook 模块异常基类.

    [职责] 所有 M-A03 业务异常的根类型
    [关联设计规范] MD-M-A03（来自DD-001）
    [属性]
      属性1: status_code int HTTP 状态码
      属性2: error_code str 业务错误码（用于 wire format）
      属性3: source str 来源系统（github|gitlab|bitbucket）
    [异常处理]
      异常1: WebhookError - 所有 M-A03 内部异常的捕获入口
    [来源标注] [DD-001:MD-M-A03]
    """


class HMACMismatchError(WebhookError):
    """HMAC 验签失败异常.

    [职责] 标记签名不匹配事件
    [关联设计规范] IC-003 / MD-M-A03（来自DD-001）
    [属性]
      属性1: source str 来源系统
      属性2: signature_valid bool 固定 False
    [状态机] 触发后进入告警计数窗口（5min > 100 → IP 封禁 1h）
    [异常处理]
      异常1: HMACMismatchError - 401 + WEBHOOK_HMAC_FAILED
    [来源标注] [DD-001:IC-003 + MD-M-A03 + AR洞察-10]
    """


class ReplayDetected(WebhookError):
    """重放检测命中异常.

    [职责] 标记 5min 窗口内已存在的 (nonce, timestamp)
    [关联设计规范] IC-003 / MD-M-A03（来自DD-001）
    [属性]
      属性1: nonce str 重复 nonce
      属性2: timestamp int 原始时间戳
    [异常处理]
      异常1: ReplayDetected - 409 + WEBHOOK_REPLAY
    [来源标注] [DD-001:IC-003 + MD-M-A03]
    """


class EnqueueError(WebhookError):
    """异步入队失败异常.

    [职责] 标记 arq 不可用或入队失败
    [关联设计规范] MD-M-A03（来自DD-001）
    [属性]
      属性1: queue_name str 目标队列
      属性2: retry_count int 已重试次数
    [异常处理]
      异常1: EnqueueError - 503, 客户端可重试
      异常2: 重试策略 - max 3 次（指数 1s/2s/4s）
    [来源标注] [DD-001:MD-M-A03]
    """
