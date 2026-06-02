"""Provider 相关 Schema — 自动检测到的 Agent CLI 信息。"""

from __future__ import annotations

from pydantic import BaseModel


class ProviderOut(BaseModel):
    name: str
    display_name: str
    binary: str
    executable_path: str
    version: str | None
    adapter: str
    description: str
    available: bool


class PingRequest(BaseModel):
    agent_system: str
    provider: str
    model: str
    api_key: str
    base_url: str | None = None


class PingResponse(BaseModel):
    ok: bool
    latency_ms: int | None = None
    error: str | None = None
