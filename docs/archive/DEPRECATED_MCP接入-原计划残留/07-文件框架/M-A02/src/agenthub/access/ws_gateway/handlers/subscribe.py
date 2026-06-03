"""subscribe / unsubscribe 事件处理 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/handlers/subscribe.py
[文件职责] 处理 subscribe/unsubscribe 事件，ACL 校验，持久化，触发回放
[所属模块] M-A02
[关联设计规范] MD-M-A02 §函数签名 on_subscribe / IC-002 §时序图
[功能描述]
  功能1: on_subscribe - 接收客户端订阅请求，ACL 校验，写 store
  功能2: on_unsubscribe - 退订并清理 store
  功能3: _check_acl - 检查 agent 是否有权订阅 topic
[输入输出]
  输入: SubscribeRequest（含 action, agent_id, topics）
  输出: 成功 → 200 ack + 触发 replay_missed；失败 → ACLError 1008
[依赖关系]
  依赖文件: models.py, exceptions.py, subscription_store.py, offline_queue.py
  被依赖文件: server.py
[注意事项]
  注意1: subscribe 必须先 _check_acl 再持久化
  注意2: subscribe 成功后必须触发 OfflineQueue.replay_missed 兜底
  注意3: topic 列表不可空，否则忽略
[代码风格] 遵循CS-MCP §1
[创建日期] 2026-06-02
[作者] DD-M-A02
[来源标注] [DD-001:MD-M-A02 + IC-002]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agenthub.access.ws_gateway.exceptions import ACLError
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.access.ws_gateway.models import SubscribeRequest
    from agenthub.access.ws_gateway.offline_queue import OfflineQueue
    from agenthub.access.ws_gateway.subscription_store import SubscriptionStore

log = get_logger(__name__)


def register(sio: Any, store: "SubscriptionStore", queue: "OfflineQueue") -> None:
    """[函数名] register
    [职责] 绑定 subscribe / unsubscribe 事件
    [来源标注] [DD-001:FS-002 handlers/subscribe.py]
    """
    ...


async def on_subscribe(sid: str, data: dict) -> None:
    """[函数名] on_subscribe
    [职责] 处理客户端 subscribe 请求，ACL 校验并持久化订阅关系
    [关联接口契约] IC-002 msg.action=subscribe
    [参数说明]
      sid: str 必填 socketio 会话 ID
      data: dict 必填 SubscribeRequest JSON
    [返回值]
      类型: None
      描述: 无返回值；成功 emit ack，失败抛 ACLError
    [错误码]
      1008 - 越权订阅
    [前置条件] sid 已 on_connect 成功
    [后置条件] subscription_store 持久化；触发 replay_missed
    [并发安全] 同一 sid 多次 subscribe 幂等
    [幂等性] 是（同 (sid, topic) 二次请求不重复持久化）
    [性能约束] P95 ≤ 50ms
    [来源标注] [DD-001:MD-M-A02 on_subscribe + IC-002]
    """
    ...


async def on_unsubscribe(sid: str, data: dict) -> None:
    """[函数名] on_unsubscribe
    [职责] 处理客户端 unsubscribe 请求，清理 store 中的订阅关系
    [关联接口契约] IC-002 msg.action=unsubscribe
    [参数说明]
      sid: str 必填
      data: dict 必填 SubscribeRequest JSON
    [后置条件] subscription_store 移除订阅
    [幂等性] 是（重复 unsubscribe 不报错）
    [来源标注] [DD-001:MD-M-A02]
    """
    ...


async def _check_acl(agent_id: str, topics: list[str]) -> None:
    """[函数名] _check_acl
    [职责] 检查 agent 对 topics 是否有订阅权限
    [参数说明]
      agent_id: str 必填
      topics: list[str] 必填
    [错误码]
      ACLError(1008) - 任一 topic 越权
    [前置条件] agent 已认证
    [后置条件] 全部 topic 通过校验或抛异常
    [并发安全] 无状态
    [来源标注] [DD-001:MD-M-A02 _check_acl + IC-002 1008]
    """
    ...
