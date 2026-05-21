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

    l1_working: list[dict] = []        # Redis 滑动窗口最近 N 条消息
    l2_summary: str | None = None      # 超长历史摘要
    l3_specs: str | None = None        # .agenthub/ 项目上下文
    l4_rag: str | None = None          # pgvector Top-K 检索结果


class AgentRequest(BaseModel):
    request_id: str                    # 全链路追踪
    session_id: UUID
    messages: list[dict]               # [{"role": "user/assistant", "content": "..."}]
    system_prompt: str | None = None
    memory: MemoryContext | None = None
    available_tools: list[str] = []
    max_tokens: int = 16000
    temperature: float = 0.7


class StreamEventType(StrEnum):
    TEXT = "text"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REQUEST_APPROVAL = "request_approval"
    TASK_PLAN = "task_plan"
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
    artifact: str | None = None        # Diff/Preview/Deploy URL


class StreamEvent(BaseModel):
    type: StreamEventType
    seq: int
    content: str | None = None
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    task_plan: dict | None = None
    metadata: dict[str, Any] = {}      # token_usage / model / latency_ms


class UnifiedAgent(ABC):
    """所有 Agent 适配器的统一接口。"""

    @abstractmethod
    def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """流式执行一次 Agent 调用，逐事件 yield。"""
        ...

    @abstractmethod
    async def chat_structured(self, prompt: str) -> dict:
        """非流式结构化调用（协调者任务分解用）。"""
        ...
