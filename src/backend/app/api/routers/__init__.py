"""REST 路由聚合。"""

from app.api.routers import (
    agents,
    attachments,
    cli,
    deploy,
    groups,
    inbox,
    providers,
    proxy,
    sessions,
    skills,
    tasks,
    templates,
)

__all__ = [
    "agents",
    "attachments",
    "cli",
    "deploy",
    "groups",
    "inbox",
    "providers",
    "proxy",
    "sessions",
    "skills",
    "tasks",
    "templates",
]
