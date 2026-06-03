"""LocalMcpInstaller（L1）：McpInstaller 端口的本期实现。

P1：做**结构校验**（transport 对应必填项），真实、确定、无环境耦合 → 可测。
P2/P3 扩展点（在此实现内补，不改端口）：
  - 真实可达性探测（远程 url HEAD/初始化握手，带超时 → E_MCP_INSTALL_TIMEOUT）
  - stdio 进程拉起 + MCP initialize 握手（依赖落在 agent 运行时侧，绑定时 attach_mcp）
  - dry-run（单 Docker + compose 资源限额，infrastructure/mcp/dry_run）
"""

from __future__ import annotations

from typing import Any

from app.domain.mcp.installer import McpInstaller
from app.domain.mcp.rules import validate_install_config


class LocalMcpInstaller(McpInstaller):
    async def probe(self, *, transport: str, merged_config: dict[str, Any]) -> None:
        # P1：结构校验（失败 → ValidationError → 422）。真实健康探测见类 docstring。
        validate_install_config(transport, merged_config)
