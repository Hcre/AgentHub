"""M-EV01 5 topic Schema 包（approval/template/process/mcp/binding）.

[文件路径] src/agenthub/eventbus/schemas/__init__.py
[文件职责] 统一导出 5 topic 的 JSON Schema（Draft 2020-12）
[所属模块] M-EV01（来自DD-001）
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01（来自DD-001）
[功能描述]
  功能1: 导出 5 topic 的 schema dict
  功能2: 暴露 SCHEMA_VERSION 常量
[输入输出]
  输入: 无
  输出: 5 个 schema 常量 + SCHEMA_VERSION
[依赖关系]
  依赖文件: agenthub.eventbus.schemas.{approval,template,process,mcp,binding}
  被依赖文件: agenthub.eventbus.registry
[注意事项]
  注意1: 所有 schema 使用 JSON Schema Draft 2020-12
  注意2: additionalProperties 默认 false（拒绝未知字段）
  注意3: 必填字段必须枚举在 required 数组
  注意4: 跨 schema 共用字段（如 trace_id/timestamp）必须统一命名
[代码风格] 遵循 CS-MCP-V1.0 §7（JSON Schema）+ §1（Python）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-EV01 - 初始版本
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + MD-MCP-V1.0-M-EV01 + CS-§7]
"""

# === 仅注释框架（无业务代码）===

# from agenthub.eventbus.schemas.approval import approval_schema
# from agenthub.eventbus.schemas.template import template_schema
# from agenthub.eventbus.schemas.process import process_schema
# from agenthub.eventbus.schemas.mcp import mcp_schema
# from agenthub.eventbus.schemas.binding import binding_schema
#
# SCHEMA_VERSION = "v1"
#
# __all__ = [
#     "approval_schema",
#     "template_schema",
#     "process_schema",
#     "mcp_schema",
#     "binding_schema",
#     "SCHEMA_VERSION",
# ]
