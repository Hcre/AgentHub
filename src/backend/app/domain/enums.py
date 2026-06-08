"""领域枚举：跨实体共享的状态/类型定义。"""

from enum import StrEnum


class AgentSystem(StrEnum):
    """适配模式：决定走 API 管道还是 CLI 运行时。"""

    CLAUDE_CODE = "claude_code"  # CLI 运行时（自带 Harness）
    PI_AGENT = "pi_agent"  # Pi Agent CLI 运行时（自带 Harness，多 Provider）
    OPENCODE = "opencode"  # OpenCode CLI 运行时（Terminal Dot）
    CODEX = "codex"  # OpenAI Codex CLI
    GEMINI = "gemini"  # Google Gemini CLI
    CURSOR_AGENT = "cursor_agent"  # Cursor CLI Agent
    ANTHROPIC_API = "anthropic_api"  # Anthropic Messages API
    OPENAI_API = "openai_api"  # OpenAI-compatible API (DeepSeek/Groq/vLLM)
    MOCK = "mock"  # 本地假数据


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    AZURE = "azure"
    MINIMAX = "minimax"
    MIMO = "mimo"
    CHATGPT = "chatgpt"  # OpenAI Codex CLI OAuth 登录
    XX = "xx"  # OpenCode 本地配置默认 provider
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
    # 用户级/命令级（SendMessageCommand 兼容值）
    AUTO = "auto"
    DIRECT = "direct"
    # 群组级（Group.dispatch_mode，影响 ChatService 群聊分流）
    AT_ROUTING = "at_routing"  # V1：@ 路由 + 死群静默
    DISCUSSION = "discussion"  # M3：Selector 回合循环
    ROLEPLAY = "roleplay"  # 预留：角色扮演（非本期）
    FREE_BROADCAST = "free_broadcast"  # 预留：自治广播（非本期）


class McpTransport(StrEnum):
    """MCP server 传输方式（MD-MCP §1.1，协议 2025-06-18）。"""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class McpServerStatus(StrEnum):
    """MCP server 审核/生命周期状态（MD-MCP §1.1）。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class McpInstallStatus(StrEnum):
    """workspace 安装状态（MD-MCP §1.2）。"""

    INSTALLING = "installing"
    READY = "ready"
    FAILED = "failed"


class McpBindingStatus(StrEnum):
    """Agent 绑定状态（MD-MCP §1.3，removed=软删）。"""

    ACTIVE = "active"
    PAUSED = "paused"
    REMOVED = "removed"


class DeploymentTarget(StrEnum):
    """部署目标类型（B-5-P2-DP01 §When-1/3/4）。"""

    STATIC_SITE = "static_site"
    CONTAINER = "container"
    PACKAGE = "package"


class DeploymentStatus(StrEnum):
    """部署状态机（B-5-P2-DP01 §6.4.4）。

    状态流转：queued → building → ready / failed
    终态：ready / failed / deleted
    """

    QUEUED = "queued"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"
