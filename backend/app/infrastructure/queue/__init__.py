"""Celery 任务队列基础设施。"""

from app.infrastructure.queue.celery_app import celery_app

__all__ = ["celery_app"]
