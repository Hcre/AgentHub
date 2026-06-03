"""M-EV01 Event Bus 模块初始化文件.

[文件路径] src/agenthub/eventbus/__init__.py
[文件职责] M-EV01 Event Bus 公共接口导出与模块初始化
[所属模块] M-EV01（来自DD-001）
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01 / IC-020 / IC-021（来自DD-001）
[功能描述]
  功能1: 导出 EventBus、StreamConsumer、TopicRegistry 公共类
  功能2: 定义模块级常量（5 主题枚举、Schema 版本、Stream 关键 topic 列表）
  功能3: 暴露 version 标识符用于运维检查
[输入输出]
  输入: 无（仅在 import 时执行）
  输出: 公开符号（EventBus / StreamConsumer / TopicRegistry / TOPIC_xxx / SCHEMA_VERSION）
[依赖关系]
  依赖文件:
    - agenthub.eventbus.bus（EventBus 主类）
    - agenthub.eventbus.stream_consumer（StreamConsumer）
    - agenthub.eventbus.registry（TopicRegistry）
    - agenthub.eventbus.schemas（5 topic schema 包）
  被依赖文件:
    - agenthub.access.ws_gateway.bus_listener（M-A02）
    - agenthub.application.pool.services（M-B02，process.spawned 消费者）
    - agenthub.application.approval.services（M-B04，approval.* 生产者）
    - agenthub.application.create.orchestrator（M-B05，mcp.created 生产者）
    - agenthub.application.binding.services（M-B03，binding.* 生产者）
    - agenthub.application.market.decorators（M-B01，mcp.updated 消费者）
[注意事项]
  注意1: 禁止在 __init__.py 中实例化 Redis 连接（必须 lazy）
  注意2: 跨模块依赖仅声明（实际调用由调用方 import），避免循环导入
  注意3: 模块标识 M-EV01 必须在所有日志/异常上下文中透传
  注意4: __all__ 列表严格控制对外暴露面，防止内部类被错误依赖
[代码风格] 遵循 CS-MCP-V1.0 §1（Python 3.11 + ruff + black + mypy strict）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-EV01 - 初始版本（FS-022 + MD-MCP-M-EV01 转化）
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + MD-MCP-V1.0-M-EV01]
"""

# === 仅注释框架（无业务代码）===
# 提示：以下为结构占位符，由开发工程师按注释契约实现

# from agenthub.core.logging import get_logger
# from agenthub.eventbus.bus import EventBus
# from agenthub.eventbus.stream_consumer import StreamConsumer
# from agenthub.eventbus.registry import TopicRegistry
# from agenthub.eventbus.schemas import (
#     approval_schema,
#     template_schema,
#     process_schema,
#     mcp_schema,
#     binding_schema,
# )
#
# __version__ = "1.0.0"  # 模块版本（与 M-EV01 关联 1.0.0）
# SCHEMA_VERSION = "v1"   # 当前 Schema 主版本
#
# # 5 个核心 topic 枚举（来自 MD-MCP-V1.0-M-EV01）
# TOPIC_APPROVAL_REQUESTED = "approval.requested"
# TOPIC_APPROVAL_DECIDED = "approval.decided"
# TOPIC_TEMPLATE_UPGRADED = "template.upgraded"
# TOPIC_PROCESS_SPAWNED = "process.spawned"
# TOPIC_PROCESS_TERMINATED = "process.terminated"
# TOPIC_MCP_CREATED = "mcp.created"
# TOPIC_MCP_UPDATED = "mcp.updated"
# TOPIC_BINDING_ACTIVE = "binding.active"
# TOPIC_BINDING_RELEASED = "binding.released"
#
# # 关键 topic 列表：强制使用 Stream 模式（来自 [AR洞察-1]）
# STREAM_TOPICS: frozenset[str] = frozenset({
#     TOPIC_APPROVAL_REQUESTED,
#     TOPIC_APPROVAL_DECIDED,
#     TOPIC_MCP_CREATED,
#     TOPIC_PROCESS_SPAWNED,
#     TOPIC_PROCESS_TERMINATED,
# })
#
# __all__ = [
#     "EventBus",
#     "StreamConsumer",
#     "TopicRegistry",
#     "SCHEMA_VERSION",
#     "STREAM_TOPICS",
#     "TOPIC_APPROVAL_REQUESTED",
#     "TOPIC_APPROVAL_DECIDED",
#     "TOPIC_TEMPLATE_UPGRADED",
#     "TOPIC_PROCESS_SPAWNED",
#     "TOPIC_PROCESS_TERMINATED",
#     "TOPIC_MCP_CREATED",
#     "TOPIC_MCP_UPDATED",
#     "TOPIC_BINDING_ACTIVE",
#     "TOPIC_BINDING_RELEASED",
# ]
