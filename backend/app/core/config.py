"""应用配置：从环境变量加载，集中管理（pydantic-settings）。"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

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
    proxy_base_url: str = "http://127.0.0.1:8000"

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
