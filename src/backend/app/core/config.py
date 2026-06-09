"""应用配置：从环境变量加载，集中管理（pydantic-settings）。"""

from functools import lru_cache
from pathlib import Path
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

    # --- reactive 前门路由（ReactiveRouter，v4 R3 由 selector_* 改名）---
    # max_discussion_rounds / selector_max_prompt_chars 已删（R3：无机械轮次上限；
    # ReactiveRouter 用硬编码 _MAX_TRANSCRIPT/_PER_MSG_CHARS，无 selector_max_prompt_chars 消费者）。
    reactive_model: str = "deepseek-v4-pro"  # reactive 决策模型
    reactive_provider: Literal["anthropic", "deepseek", "openai"] = "deepseek"
    deepseek_api_key: str = ""  # DeepSeek API Key

    # --- 任务编排（Coordinator / Planner）---
    # Planner 的 LLM 完全可配置：provider + model + base_url + key 任意组合，不锁定单一模型。
    coordinator_provider: Literal["anthropic", "openai", "deepseek"] = "deepseek"
    coordinator_model: str = "deepseek-chat"  # Planner 默认用 DeepSeek
    coordinator_base_url: str = ""  # openai 兼容自定义端点（deepseek/groq/vllm…）
    coordinator_api_key: str = ""  # 空 → 回退 provider 默认 key（deepseek/openai/anthropic）

    # --- 记忆系统 MCP ---
    # MCP_MEMORY_URL 非空时，CLI spawn 注入 --mcp-config，Agent 可调用 save_memory tool
    # 路径 = 记忆协议服务端 mount 点（main.py /api/mcp-memory）+ /sse（与 /api/mcp REST 分离）
    mcp_memory_url: str = ""  # 例：http://127.0.0.1:8000/api/mcp-memory/sse

    # --- 步骤终结工具 MCP (coordinator v3) ---
    # MCP_STEP_TOOLS_URL 非空时，worker CLI spawn 注入 step-tools server（task_complete/ask）
    mcp_step_tools_url: str = "http://127.0.0.1:8000/api/step-tools/sse"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- 技能市场 ---
    # skill 安装根目录（zip 解到这里，已安装列表扫这里）
    # 默认 .agenthub/skills（相对 cwd，可被环境变量 SKILLS_DIR 覆盖）
    skills_dir: str = ".agenthub/skills"

    # --- 模板市场 ---
    # 模板存储根目录（git clone 落这里、本地模板也写这里）
    # 默认 .agenthub/templates（相对 cwd，可被环境变量 TEMPLATES_DIR 覆盖）
    templates_dir: str = ".agenthub/templates"

    @property
    def skills_dir_path(self) -> Path:
        return Path(self.skills_dir).resolve()

    @property
    def templates_dir_path(self) -> Path:
        return Path(self.templates_dir).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取环境变量。"""
    return Settings()


settings = get_settings()
