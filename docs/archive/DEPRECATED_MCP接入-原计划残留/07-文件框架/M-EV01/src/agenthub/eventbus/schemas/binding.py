"""M-EV01 binding topic Schema（binding.active / binding.released）.

[文件路径] src/agenthub/eventbus/schemas/binding.py
[文件职责] binding.* topic JSON Schema
[所属模块] M-EV01
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01
[创建日期] 2026-06-03
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + TD:BR-001~004]
"""

# binding_active_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/binding/active/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "BindingActive",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["binding_id", "workspace_id", "mcp_id", "trace_id", "emitted_at"],
#     "properties": {
#         "binding_id": {"type": "string", "format": "uuid"},
#         "workspace_id": {"type": "string", "format": "uuid"},
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# binding_released_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/binding/released/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "BindingReleased",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["binding_id", "workspace_id", "mcp_id", "trace_id", "emitted_at"],
#     "properties": {
#         "binding_id": {"type": "string", "format": "uuid"},
#         "workspace_id": {"type": "string", "format": "uuid"},
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# binding_schema: dict[str, object] = {
#     "active": binding_active_schema,
#     "released": binding_released_schema,
#     "version": "v1",
# }
