"""仓储抽象接口（L2 定义，L1 实现 —— 依赖倒置）。"""

from app.domain.repositories.agent_repository import AgentRepository
from app.domain.repositories.message_repository import MessageRepository
from app.domain.repositories.session_repository import SessionRepository
from app.domain.repositories.task_repository import TaskRepository

__all__ = [
    "AgentRepository",
    "MessageRepository",
    "SessionRepository",
    "TaskRepository",
]
