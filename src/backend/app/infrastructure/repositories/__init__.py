"""L1 仓储实现（实现 L2 抽象接口）。"""

from app.infrastructure.repositories.agent_repository import PostgresAgentRepository
from app.infrastructure.repositories.deployment_repository import (
    PostgresDeploymentRepository,
)
from app.infrastructure.repositories.group_repository import PostgresGroupRepository
from app.infrastructure.repositories.inbox_repository import PostgresInboxRepository
from app.infrastructure.repositories.mcp_repository import (
    PostgresMcpBindingRepository,
    PostgresMcpInstallationRepository,
    PostgresMcpServerRepository,
)
from app.infrastructure.repositories.memory_repository import PostgresMemoryRepository
from app.infrastructure.repositories.message_repository import (
    PostgresMessageRepository,
)
from app.infrastructure.repositories.session_repository import (
    PostgresSessionRepository,
)
from app.infrastructure.repositories.task_repository import PostgresTaskRepository
from app.infrastructure.repositories.template_repository import (
    PostgresTemplateRepository,
)
from app.infrastructure.repositories.usage_repository import PostgresUsageRepository

__all__ = [
    "PostgresAgentRepository",
    "PostgresDeploymentRepository",
    "PostgresGroupRepository",
    "PostgresInboxRepository",
    "PostgresMcpBindingRepository",
    "PostgresMcpInstallationRepository",
    "PostgresMcpServerRepository",
    "PostgresMemoryRepository",
    "PostgresMessageRepository",
    "PostgresSessionRepository",
    "PostgresTaskRepository",
    "PostgresTemplateRepository",
    "PostgresUsageRepository",
]
