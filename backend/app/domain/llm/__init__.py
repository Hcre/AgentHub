"""统一 Agent 适配器抽象（对应 plan_sections/adapter_interface_spec.md）。

L2 定义 UnifiedAgent 抽象 + StreamEvent 协议，L1 提供 Claude/Mock 等实现。
"""

from app.domain.llm.protocol import (
    AgentRequest,
    AgentRuntime,
    LLMAdapter,
    MemoryContext,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolResult,
    UnifiedAgent,
)

__all__ = [
    "AgentRequest",
    "AgentRuntime",
    "LLMAdapter",
    "MemoryContext",
    "StreamEvent",
    "StreamEventType",
    "ToolCall",
    "ToolResult",
    "UnifiedAgent",
]
