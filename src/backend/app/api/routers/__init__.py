"""REST 路由聚合。"""

from app.api.routers import agents, groups, inbox, providers, proxy, sessions, skills, tasks

__all__ = ["agents", "groups", "inbox", "providers", "proxy", "sessions", "skills", "tasks"]
