"""应用配置：从环境变量加载，集中管理（pydantic-settings）。"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- 运行环境 ---
    env: Literal["development", "production", "test"] = "development"
    debug: bool = True

    # --- 数据库 ---
    database_url: str = "postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- 安全 ---
    secret_key: str = "CHANGE_ME_base64_32bytes"
    jwt_secret: str = "CHANGE_ME_jwt_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # --- LLM Adapter ---
    llm_adapter_mode: Literal["claude_cli", "anthropic_api", "mock"] = "mock"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"

    # --- 上下文 / L1 记忆 ---
    l1_window_size: int = 20
    max_tokens: int = 16000
    max_tool_turns: int = 10
    claude_cli_timeout: int = 300
    proxy_base_url: str = "http://127.0.0.1:9001"

    # --- Claude Code 长驻进程（Phase 1，见 ADR-02）---
    # False = V0：每次请求 spawn 新进程 + --resume 复用历史
    # True  = V1：长驻进程 + --input-format stream-json，stdin JSONL 多轮注入
    claude_code_long_running: bool = False
    # 软上限：超过仅 warning（用于发现配置问题）
    claude_code_pool_soft_max: int = 32
    # 硬上限：超过按 LRU 淘汰，防止 OOM（Step 3）
    claude_code_pool_hard_max: int = 64
    # idle TTL：handle 超过这个秒数未使用 → 后台 sweeper 淘汰（Step 3）
    claude_code_idle_ttl_seconds: int = 300
    # idle sweeper 扫描周期（Step 3）
    claude_code_idle_sweep_interval: int = 60

    # --- 群聊增量注入 ---
    max_delta_messages: int = 50  # ContextBuilder delta 上限，超过截断
    watermark_ttl_seconds: int = 604800  # Watermark Redis TTL (7天)

    # --- 讨论模式 ---
    max_discussion_rounds: int = 3  # DiscussionOrchestrator 硬上限
    selector_model: str = "deepseek-chat"  # Selector 廉价模型（默认 DeepSeek V4 Flash）
    selector_provider: Literal["anthropic", "deepseek", "openai"] = "deepseek"
    deepseek_api_key: str = ""  # DeepSeek API Key
    selector_max_prompt_chars: int = 4000  # Selector prompt 总字符上限

    # --- 记忆系统 MCP ---
    # MCP_MEMORY_URL 非空时，CLI spawn 注入 --mcp-config，Agent 可调用 save_memory tool
    # 路径 = 记忆协议服务端 mount 点（main.py /api/mcp-memory）+ /sse（与 /api/mcp REST 分离）
    mcp_memory_url: str = ""   # 例：http://127.0.0.1:8000/api/mcp-memory/sse

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取环境变量。"""
    return Settings()


settings = get_settings()
