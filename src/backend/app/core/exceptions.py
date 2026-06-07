"""领域与应用层异常，由 L4 统一映射为 HTTP 响应。"""


class AgentHubError(Exception):
    """所有自定义异常的基类。"""


class DomainError(AgentHubError):
    """领域规则违反（如 Agent 名称重复、非法状态流转），映射 400/409。"""


class NotFoundError(AgentHubError):
    """资源不存在，映射 404。"""


class PermissionError(AgentHubError):  # - 领域语义优先
    """权限不足，映射 403。"""


class InvalidTransitionError(DomainError):
    """Task FSM 非法状态转换。"""


class ValidationError(AgentHubError):
    """输入校验失败（通过 schema 但违反业务规则，如成员 Agent 不存在），映射 422。"""


class SyncError(AgentHubError):
    """外部同步失败（git clone/pull 失败、上游不可用），映射 502。"""
