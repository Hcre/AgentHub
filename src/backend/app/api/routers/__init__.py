"""REST 路由聚合。"""
from app.api.routers import (
    agents,
    attachments,
    deploy,
    groups,
    inbox,
    providers,
    proxy,
    sessions,
    skills,
    tasks,
)

__all__ = [
    "agents",
    "attachments",
    "deploy",
    "groups",
    "inbox",
    "providers",
    "proxy",
    "sessions",
    "skills",
    "tasks",
]
