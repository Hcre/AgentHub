"""M-EV01 mcp topic Schema（mcp.created / mcp.updated）.

[文件路径] src/agenthub/eventbus/schemas/mcp.py
[文件职责] mcp.* topic JSON Schema
[所属模块] M-EV01
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01 / IC-007
[创建日期] 2026-06-03
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + IC-007 + DDR-005]
"""

# mcp_created_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/mcp/created/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "MCPCreated",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["mcp_id", "version", "trace_id", "emitted_at"],
#     "properties": {
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "version": {"type": "string"},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# mcp_updated_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/mcp/updated/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "MCPUpdated",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["mcp_id", "version", "trace_id", "emitted_at"],
#     "properties": {
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "version": {"type": "string"},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# mcp_schema: dict[str, object] = {
#     "created": mcp_created_schema,
#     "updated": mcp_updated_schema,
#     "version": "v1",
# }
