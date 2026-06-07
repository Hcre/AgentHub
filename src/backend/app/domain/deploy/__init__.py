"""L2 领域层：部署卡（Deployment）。

实现：
- Deployment 聚合根（含 4 态状态机：queued → building → ready/failed）
- DeploymentPlan 计划值对象（前端传入 + 内部 L3 包装）
- 部署阶段（stage）枚举：上传 → 构建 → 启动 → 运行

依据：
- docs/specs/04-commands §2 / §6.4.4 B-5-P2-DP01
- docs/specs/03-data-model §Deployment（待 PR-09 同步，本期先内联）
- docs/plan/开发清单_roadmap §8.3 P2 缺口「部署发布」

依赖规则：纯 L2，不依赖任何上层（L3/L4/L5），仅使用 Pydantic/标准库。
"""

from app.domain.deploy.deployment import (
    Deployment,
    DeploymentPlan,
    DeploymentStage,
    TERMINAL_DEPLOYMENT_STATUSES,
    is_terminal_deployment_status,
    transition_deployment,
)
from app.domain.deploy.errors import (
    DeployBuildError,
    DeployInvalidStageError,
    DeployInvalidTransitionError,
    DeployNotFoundError,
    DeployValidationError,
)

__all__ = [
    "Deployment",
    "DeploymentPlan",
    "DeploymentStage",
    "TERMINAL_DEPLOYMENT_STATUSES",
    "is_terminal_deployment_status",
    "transition_deployment",
    "DeployBuildError",
    "DeployInvalidStageError",
    "DeployInvalidTransitionError",
    "DeployNotFoundError",
    "DeployValidationError",
]
