"""M-EV01 process topic Schema（process.spawned / process.terminated）.

[文件路径] src/agenthub/eventbus/schemas/process.py
[文件职责] process.* topic JSON Schema
[所属模块] M-EV01
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01 / IC-004
[创建日期] 2026-06-03
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + IC-004]
"""

# process_spawned_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/process/spawned/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "ProcessSpawned",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["mcp_id", "workspace_id", "pid", "state", "trace_id", "emitted_at"],
#     "properties": {
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "workspace_id": {"type": "string", "format": "uuid"},
#         "pid": {"type": "integer", "minimum": 1},
#         "state": {"enum": ["running", "reserved"]},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# process_terminated_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/process/terminated/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "ProcessTerminated",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["mcp_id", "workspace_id", "pid", "exit_code", "reason", "trace_id", "emitted_at"],
#     "properties": {
#         "mcp_id": {"type": "string", "format": "uuid"},
#         "workspace_id": {"type": "string", "format": "uuid"},
#         "pid": {"type": "integer", "minimum": 1},
#         "exit_code": {"type": "integer"},
#         "reason": {"enum": ["normal", "killed", "oom", "timeout", "spawn_failed"]},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# process_schema: dict[str, object] = {
#     "spawned": process_spawned_schema,
#     "terminated": process_terminated_schema,
#     "version": "v1",
# }
