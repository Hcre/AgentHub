"""Deploy Pydantic 请求/响应模型（P2 §4.2.4 + BDD `B-5-P2-DP01`）。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentStartRequest(BaseModel):
    """POST /api/deployments 请求体。"""

    session_id: UUID
    target: Literal["static_site", "container", "package"]
    entry_file: str | None = Field(default=None, max_length=256)
    framework: str | None = Field(default=None, max_length=64)
    files: dict[str, str] = Field(
        default_factory=dict,
        description="相对路径 → 文件内容。static_site 必含 entry_file。",
    )


class DeploymentOut(BaseModel):
    """部署响应（POST/GET/DELETE 共用）。"""

    id: UUID
    session_id: UUID
    owner_id: UUID | None = None
    target: str
    entry_file: str | None = None
    framework: str | None = None
    status: str
    stage: str | None = None
    progress: float = 0.0
    preview_url: str | None = None
    download_url: str | None = None
    build_logs: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    ttl: int = 3600
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
