"""M-A03 WebhookApp FastAPI 入口.

[文件路径] src/agenthub/access/webhook/app.py
[文件职责] 独立端口的 Webhook 接收应用入口（Chain of Responsibility 编排）
[所属模块] M-A03（来自DD-001）
[关联设计规范] FS-003 / MD-M-A03 / IC-003（来自DD-001）
[功能描述]
  功能1: 启动独立 ASGI app（与 M-A01 端口隔离，避免资源争抢）
  功能2: 注册 /webhook/{source} 路由（github|gitlab|bitbucket）
  功能3: 编排 HMAC 验签 → 重放校验 → 异步入队 责任链
  功能4: 立即返回 200 ack（异步处理，避开上游超时）
[输入输出]
  输入: HTTP POST 请求（raw payload + 签名头 + 时间戳头）
  输出: 200 + {ack: true, trace_id} | 401/409/429/503 + {code, message}
[依赖关系]
  依赖文件: verifiers/* (Chain) / replay_guard.py / enqueuer.py / exceptions.py
  被依赖文件: 部署入口 (uvicorn/gunicorn) / M-D02 metrics
[注意事项]
  注意1: 与 M-A01 解耦——独立进程独立端口，禁止共享 app 实例
  注意2: 必须立即 200 ack（处理 P95 ≤ 100ms）
  注意3: 失败计数（5min>100 封 IP 1h，[AR洞察-10]）
[代码风格] 遵循CS-MCP-V1.0 §1.2/§1.3/§1.8
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本
[作者] DD-M-A03-20260603
[来源标注] [DD-001:FS-003 + MD-M-A03 + IC-003]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from agenthub.access.webhook.enqueuer import Enqueuer
from agenthub.access.webhook.replay_guard import ReplayGuard
from agenthub.access.webhook.verifiers.base import HMACVerifier
from agenthub.access.webhook.verifiers.bitbucket import BitbucketVerifier
from agenthub.access.webhook.verifiers.github import GitHubVerifier
from agenthub.access.webhook.verifiers.gitlab import GitLabVerifier
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.core.config import Settings

log = get_logger(__name__)


class WebhookApp:
    """Webhook 接收应用.

    [职责] 独立 ASGI 应用，注册路由并编排 Chain of Responsibility
    [关联设计规范] MD-M-A03（来自DD-001）
    [属性]
      属性1: app FastAPI FastAPI 实例
      属性2: settings Settings 配置（端口、限流、Vault 路径）
      属性3: verifiers dict[str, HMACVerifier] 来源→验签器映射
      属性4: replay_guard ReplayGuard 重放守卫
      属性5: enqueuer Enqueuer 异步入队器
    [方法列表]
      方法1: handle(source, request) -> Response - 路由处理入口（IC-003 实现）
      方法2: register_routes() -> None - 注册 /webhook/{source}
      方法3: register_middleware() -> None - 注册 trace_id / metrics
    [状态机] 无状态（应用常驻；verifier cache 可选）
    [异常处理]
      异常1: HMACMismatchError - 401 + WEBHOOK_HMAC_FAILED + 计数告警
      异常2: ReplayDetected - 409 + WEBHOOK_REPLAY
      异常3: EnqueueError - 503 + 客户端重试
    [来源标注] [DD-001:MD-M-A03 + IC-003]
    """

    def __init__(
        self,
        settings: Settings,
        replay_guard: ReplayGuard,
        enqueuer: Enqueuer,
    ) -> None:
        """初始化 WebhookApp.

        [函数名] __init__
        [职责] 构造 FastAPI 实例并组装 Chain of Responsibility
        [参数说明]
          参数1: settings Settings 必填 配置对象（端口/Vault 路径/限流阈值）
          参数2: replay_guard ReplayGuard 必填 重放守卫实例
          参数3: enqueuer Enqueuer 必填 异步入队器实例
        [返回值] None
        [前置条件] Vault 中各 source secret 已就绪
        [后置条件] self.app 已就绪可启动 uvicorn
        [并发安全] 线程安全（FastAPI app 共享）
        [来源标注] [DD-001:MD-M-A03]
        """
        ...

    async def handle(self, source: str, request: Request) -> Response:
        """路由处理入口（IC-003 webhook.handle 实现）.

        [函数名] handle
        [职责] 接收 webhook → 验签 → 重放检测 → 入队 → 立即 200 ack
        [关联接口契约] IC-003（来自DD-001）
        [参数说明]
          参数1: source str 必填 URL 路径参数 github|gitlab|bitbucket
          参数2: request Request 必填 FastAPI Request（raw body + headers）
        [返回值]
          类型: Response
          描述: 200 + {ack: true, trace_id} 或错误码 + {code, message}
        [错误码]
          错误码1: WEBHOOK_HMAC_FAILED 401 验签失败
          错误码2: WEBHOOK_REPLAY 409 重放命中
          错误码3: WEBHOOK_RATE_LIMIT 429 限流
          错误码4: WEBHOOK_ENQUEUE_FAILED 503 arq 不可用
        [前置条件] Vault secret 可用；Redis nonce 表可写
        [后置条件] 成功事件入 arq 队列；失败计数累加
        [并发安全] 无状态；线程安全
        [幂等性] 是；幂等键 payload SHA256 + timestamp；5min 窗口；返回上次 ack
        [性能约束] P95 ≤ 100ms（仅 ack 阶段）
        [来源标注] [DD-001:IC-003 + MD-M-A03]
        """
        ...

    def register_routes(self) -> None:
        """注册 /webhook/{source} 路由.

        [函数名] register_routes
        [职责] 将 POST /webhook/{source} 绑定到 self.handle
        [参数说明] 无
        [返回值] None
        [来源标注] [DD-M推断:依据 FastAPI 路由注册规范]
        """
        ...

    def register_middleware(self) -> None:
        """注册 trace_id 注入与 metrics 中间件.

        [函数名] register_middleware
        [职责] 注入 X-Trace-ID 上报请求计数与延迟
        [参数说明] 无
        [返回值] None
        [来源标注] [DD-M推断:依据 M-A01 TraceMiddleware 同构]
        """


class WebhookAck(BaseModel):
    """Webhook ack 响应模型.

    [职责] 200 ack 的 wire format
    [关联设计规范] IC-003（来自DD-001）
    [属性]
      属性1: ack bool 固定 true
      属性2: trace_id str 本次请求的链路追踪 ID
    [来源标注] [DD-001:IC-003]
    """
    ack: bool
    trace_id: str
