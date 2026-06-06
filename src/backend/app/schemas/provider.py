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


class DefaultConfigOut(BaseModel):
    """CLI 进程级 provider 的默认连接配置（前端 Step 2 选中后回填用）。

    字段从 CLI 本地配置文件读取，读不到时返 None（不兑底硬编码，
    让用户明确知道"本地没配置"）。
    """
    agent_system: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    provider: str | None = None
    source: str | None = None  # 实际读到的配置文件路径（null = 没找到）
    note: str | None = None
