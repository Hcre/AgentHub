"""Celery 应用：以 Redis 为 broker/backend。

MVP 阶段任务执行可降级为内存/直接 await；Worker 调度在 M3 接入 DAG Canvas。
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "agenthub",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=600,
)


@celery_app.task(name="agenthub.ping")
def ping() -> str:
    """健康检查任务。"""
    return "pong"
