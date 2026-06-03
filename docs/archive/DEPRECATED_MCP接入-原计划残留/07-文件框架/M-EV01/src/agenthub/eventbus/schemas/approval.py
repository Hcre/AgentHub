"""M-EV01 approval topic Schema（approval.requested / approval.decided）.

[文件路径] src/agenthub/eventbus/schemas/approval.py
[文件职责] approval.* topic 的 JSON Schema 定义（Draft 2020-12）
[所属模块] M-EV01
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01 / IC-005 / IC-006
[功能描述]
  功能1: 定义 approval.requested 事件 payload schema
  功能2: 定义 approval.decided 事件 payload schema
[输入输出]
  输入: 无（仅 schema 常量）
  输出: approval_requested_schema / approval_decided_schema
[依赖关系]
  依赖文件: 无
  被依赖文件: agenthub.eventbus.schemas.__init__
[注意事项]
  注意1: 关键 topic（强制 stream 模式）
  注意2: trace_id 必填（用于跨链路追踪）
  注意3: timestamp 必填 ISO8601
[代码风格] CS-§7 JSON Schema 2020-12
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-EV01 - 初始版本
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + IC-005 + IC-006]
"""

# === 仅注释框架（无业务代码）===

# approval_requested_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/approval/requested/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "ApprovalRequested",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["queue_id", "workspace_id", "mcp_id", "tool", "args_hash", "trace_id", "emitted_at"],
#     "properties": {
#         "queue_id": {"type": "string", "format": "uuid"},
#         "workspace_id": {"type": "string", "format": "uuid"},
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "tool": {"type": "string", "maxLength": 64},
#         "args_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# approval_decided_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/approval/decided/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "ApprovalDecided",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["queue_id", "decision", "decider", "trace_id", "emitted_at"],
#     "properties": {
#         "queue_id": {"type": "string", "format": "uuid"},
#         "decision": {"enum": ["allow", "deny"]},
#         "decider": {"type": "string", "format": "uuid"},
#         "decision_id": {"type": "string", "format": "uuid"},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# approval_schema: dict[str, object] = {
#     "requested": approval_requested_schema,
#     "decided": approval_decided_schema,
#     "version": "v1",
# }
