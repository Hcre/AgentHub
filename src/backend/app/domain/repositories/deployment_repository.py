"""DeploymentRepository 抽象接口（L2 定义，L1 实现）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.deploy.deployment import Deployment


class DeploymentRepository(ABC):
    @abstractmethod
    async def save(self, deployment: Deployment) -> None: ...

    @abstractmethod
    async def get_by_id(self, deployment_id: UUID) -> Deployment | None: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: UUID, *, include_deleted: bool = False
    ) -> list[Deployment]:
        """按 session 列部署（默认排除 deleted 软删记录）。"""
        ...
