"""DeploymentProgress 领域事件（M4①.1）。"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True)
class DeploymentProgress(DomainEvent):
    deployment_id: UUID
    status: str  # queued / building / ready / failed
    stage: str | None = None
    preview_url: str | None = None