"""M-EV01 template topic Schema（template.upgraded）.

[文件路径] src/agenthub/eventbus/schemas/template.py
[文件职责] template.* topic JSON Schema
[所属模块] M-EV01
[关联设计规范] FS-022 / MD-MCP-V1.0-M-EV01 / IC-010
[创建日期] 2026-06-03
[作者] DD-M-EV01-20260603
[来源标注] [DD-001:FS-022 + IC-010]
"""

# template_upgraded_schema: dict[str, object] = {
#     "$id": "agenthub://eventbus/schemas/template/upgraded/v1",
#     "$schema": "https://json-schema.org/draft/2020-12/schema",
#     "title": "TemplateUpgraded",
#     "type": "object",
#     "additionalProperties": False,
#     "required": ["template_id", "version", "diff", "trace_id", "emitted_at"],
#     "properties": {
#         "template_id": {"type": "string", "format": "uuid"},
#         "version": {"type": "string"},
#         "diff": {"type": "array", "items": {"type": "object"}},
#         "trace_id": {"type": "string", "minLength": 1},
#         "emitted_at": {"type": "string", "format": "date-time"},
#     },
# }
#
# template_schema: dict[str, object] = {
#     "upgraded": template_upgraded_schema,
#     "version": "v1",
# }
