"""MCP 领域子包（L2 Domain）：实体 + 业务规则。

与现有 `domain/llm/`、`domain/task_engine/` 子包先例一致；不依赖 ORM/框架（AR-01）。
落地口径见 `docs/plan/后续升级计划/MCP接入/README-REVISION.md` §9（二次对账）。
"""

from app.domain.mcp.mcp_binding import AgentMcpBinding
from app.domain.mcp.mcp_installation import WorkspaceMcpInstallation
from app.domain.mcp.mcp_server import McpServer

__all__ = ["AgentMcpBinding", "McpServer", "WorkspaceMcpInstallation"]
