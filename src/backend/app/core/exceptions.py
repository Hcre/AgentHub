"""领域与应用层异常，由 L4 统一映射为 HTTP 响应。"""


class AgentHubError(Exception):
    """所有自定义异常的基类。"""


class DomainError(AgentHubError):
    """领域规则违反（如 Agent 名称重复、非法状态流转），映射 400/409。"""


class NotFoundError(AgentHubError):
    """资源不存在，映射 404。"""


class PermissionError(AgentHubError):  # - 领域语义优先
    """权限不足，映射 403。"""


class AuthRequiredError(PermissionError):
    """需要鉴权但未提供或鉴权失败，映射 401。

    M5 鉴权降级契约 (per docs/specs/04-commands §6.1.6 B-1-P0-04 + plan_agenthub-m5-m6):
    - 业务权限不足 (msg.user_id != current_user) → PermissionError → 403
    - 鉴权缺失 + 无 fallback (system message) → AuthRequiredError → 401
    区别于 PermissionError 避免被统一映射为 403。
    """


class InvalidTransitionError(DomainError):
    """Task FSM 非法状态转换。"""


class ValidationError(AgentHubError):
    """输入校验失败（通过 schema 但违反业务规则，如成员 Agent 不存在），映射 422。"""
