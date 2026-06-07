"""Deploy 域错误类型（区别于 core.exceptions，部署专属错误码以 E_DEPLOY_ 前缀）。"""

from __future__ import annotations

from app.core.exceptions import AgentHubError, DomainError, NotFoundError


class DeployValidationError(AgentHubError):
    """部署入参校验失败（target 非法 / 缺 entry_file / framework 不匹配）。"""


class DeployInvalidTransitionError(DomainError):
    """Deployment 状态机非法流转（read-only / deleted / 倒退）。"""


class DeployInvalidStageError(AgentHubError):
    """阶段序列非法（如跳过 uploading 直入 starting）。"""


class DeployBuildError(AgentHubError):
    """构建失败（index.html 引用不存在脚本 / 容器构建超时 / 网络不可达）。"""

    def __init__(self, message: str, *, code: str = "E_DEPLOY_BUILD_FAILED") -> None:
        super().__init__(message)
        self.code = code


class DeployNotFoundError(NotFoundError):
    """部署记录不存在。"""
