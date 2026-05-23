"""REST 路由聚合。"""

from app.api.routers import agents, groups, inbox, proxy, sessions, tasks

__all__ = ["agents", "groups", "inbox", "proxy", "sessions", "tasks"]
