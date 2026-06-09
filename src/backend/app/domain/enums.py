"""领域枚举：跨实体共享的状态/类型定义。"""

import sys
from enum import Enum

# StrEnum 在 Python 3.11+ 提供；3.10 用 Enum + str
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Backward compatibility for Python 3.10."""
        pass


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
    # v4 调度态（7 个，下限）。详见 coordinator-v4-R1 §8：
    # 「两态」（DONE/NOT DONE）是 WorkerOutcome 维度，非 TaskStatus；
    # not_done 的节点停在 RUNNING，不单列状态。
    # 已删 QUEUED（串行下 RUNNING 前一瞬间，无观察窗口）、
    # PAUSED（= RUNNING，worker 等回复和在跑没区别）、
    # AWAITING_APPROVAL（死代码，无产出方）。
    PENDING = "pending"
    RUNNING = "running"
    VERIFYING = "verifying"  # worker 报完成，验证闸门进行中（COMPLETED = 已验证）
    BLOCKED = "blocked"  # 上游 FAILED 导致不可达；上游修复后回 PENDING
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


class InboxItemStatus(StrEnum):
    """收件箱条目生命周期（M4 审批流）。"""

    UNREAD = "unread"
    READ = "read"
    RESOLVED = "resolved"  # 审批已批准/驳回，从未决列表移除


class InboxResolution(StrEnum):
    """审批结果（type=approval 的条目 resolve 时回填）。"""

    APPROVED = "approved"
    REJECTED = "rejected"


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
