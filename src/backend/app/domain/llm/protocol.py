"""UnifiedAgent 协议与 StreamEvent 模型（域2↔域3 接口契约，W1 冻结）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MemoryContext(BaseModel):
    """域3 记忆系统打包，注入到每次 Agent 调用。"""

    l1_working: list[dict] = []  # Redis 滑动窗口最近 N 条消息
    l2_summary: str | None = None  # 超长历史摘要
    l3_specs: str | None = None  # .agenthub/ 项目上下文
    l4_rag: str | None = None  # pgvector Top-K 检索结果


class AgentRequest(BaseModel):
    request_id: str  # 全链路追踪
    session_id: UUID
    messages: list[dict]  # [{"role": "user/assistant", "content": "..."}]
    system_prompt: str | None = None
    memory: MemoryContext | None = None
    available_tools: list[str] = []
    max_tokens: int = 16000
    temperature: float = 0.7
    # 群聊上下文（私聊场景留空，CLI session key 等据此分流）
    agent_id: UUID | None = None  # 本次调用的目标 Agent（群聊必填）
    group_id: UUID | None = None  # 所在群组（群聊必填）
    is_group_chat: bool = False  # 群聊标识；True 时 CLI key = uuid5(session_id:agent_id)
    # 工作空间（CLI 进程 cwd — 宿主机绝对路径或 WSL 映射路径）
    working_directory: str | None = None
    # 群聊 delta 文本（自上次发言后的新消息渲染）。从 system_prompt 中独立出来，
    # 是为了让 V1 长驻进程能复用 spawn-time 的稳定 sp（persona + 契约 + 成员），
    # 把动态 delta 放到 user message 里逐轮注入。V0 路径会拼回 sp 保持兼容。
    # 见 ADR-02 + ContextBuilder._build_group。
    group_delta_text: str | None = None
    # DB 查询结果：session 是否已有 assistant 消息（决定 CLI --resume vs --session-id）
    has_history: bool = False
    # MCP 绑定（P2 请求携带）：L3 binding service 解析 agent active bindings →
    # 序列化为 MCP 2025-06-18 config 条目，runtime 在 build_cmd 时合并写入 .mcp.json。
    # 每条形如 {"name","type":"stdio|sse|http","command"/"url",...}。见 ADR-05 / §MCP.2。
    mcp_servers: list[dict] = []


class StreamEventType(StrEnum):
    TEXT = "text"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REQUEST_APPROVAL = "request_approval"
    TASK_PLAN = "task_plan"
    TASK_UPDATE = "task_update"  # 协调者任务状态变更（running/done/failed），WS 推前端进度
    TASK_ACTIVITY = "task_activity"  # worker 实时活动（text/tool_call/tool_result），归到步骤进度 feed
    ERROR = "error"
    DONE = "done"


class ToolCall(BaseModel):
    call_id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    call_id: str
    success: bool
    content: str | None = None
    error: str | None = None
    artifact: str | None = None  # Diff/Preview/Deploy URL


class StreamEvent(BaseModel):
    type: StreamEventType
    seq: int
    content: str | None = None
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    task_plan: dict | None = None
    metadata: dict[str, Any] = {}  # token_usage / model / latency_ms
    # 群聊场景下标识发言人，前端按此给气泡分色（私聊为 None）
    sender_agent_id: UUID | None = None


class LLMAdapter(ABC):
    """无状态 API 管道（Anthropic API / OpenAI-compatible API）。

    每次调用独立，不持有进程或会话状态。
    L3 负责记忆注入和工具编排。
    """

    @abstractmethod
    def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """流式执行一次 LLM 调用，逐事件 yield。"""
        ...

    @abstractmethod
    async def chat_structured(self, prompt: str) -> dict:
        """非流式结构化调用（协调者任务分解用）。"""
        ...


class AgentRuntime(ABC):
    """有状态 CLI 运行时（Claude Code / Codex 等自带 Harness 的工具）。

    管理子进程生命周期，解析 stream-json 输出。
    工具执行、会话记忆、权限由 CLI 自身 Harness 处理。
    """

    @abstractmethod
    def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """启动 CLI 进程并流式解析输出。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """终止运行中的 CLI 进程。"""
        ...


# 联合类型：factory 返回值
UnifiedAgent = LLMAdapter | AgentRuntime
