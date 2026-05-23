"""领域枚举：跨实体共享的状态/类型定义。"""

from enum import StrEnum


class AgentSystem(StrEnum):
    """适配模式：决定走 API 管道还是 CLI 运行时。"""

    CLAUDE_CODE = "claude_code"        # CLI 运行时（自带 Harness）
    ANTHROPIC_API = "anthropic_api"    # Anthropic Messages API
    OPENAI_API = "openai_api"          # OpenAI-compatible API (DeepSeek/Groq/vLLM)
    MOCK = "mock"                      # 本地假数据


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    AZURE = "azure"
    SYSTEM = "system"  # 协调者使用


class AgentStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class SessionType(StrEnum):
    GROUP = "group"
    PRIVATE = "private"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContentType(StrEnum):
    TEXT = "text"
    DIFF = "diff"
    PREVIEW_CARD = "preview_card"
    TASK_PLAN = "task_plan"
    APPROVAL_REQUEST = "approval_request"
    FILE = "file"


class MessageStatus(StrEnum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskSource(StrEnum):
    CHAT = "chat"
    MANUAL = "manual"


class NotificationCategory(StrEnum):
    APPROVAL = "approval"
    TASK = "task"
    SYSTEM = "system"
    CALENDAR = "calendar"


class DispatchMode(StrEnum):
    AUTO = "auto"
    DIRECT = "direct"
