"""McpInstaller 端口（L2 Domain）：安装/健康探针抽象。

依赖倒置（AR-01）：L3 依赖本端口，L1 提供实现。P1 实现做结构校验（真实、可测）；
真实可达性/进程拉起/资源探针是 P2/P3 的扩展点（在实现内补，不改本端口签名）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class McpInstaller(ABC):
    @abstractmethod
    async def probe(self, *, transport: str, merged_config: dict[str, Any]) -> None:
        """安装探针。校验/探测失败抛领域异常（ValidationError→422 / DomainError→409）。

        merged_config = server.config_json 叠加 install.config_overrides。
        """
        ...
