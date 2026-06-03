"""M-A03 Webhook Receiver 模块入口.

[文件路径] src/agenthub/access/webhook/__init__.py
[文件职责] 暴露 Webhook Receiver 公共接口，初始化模块导出表
[所属模块] M-A03（来自DD-001）
[关联设计规范] FS-003 / MD-M-A03（来自DD-001）
[功能描述]
  功能1: 导出 WebhookApp / HMACVerifier / ReplayGuard / Enqueuer
  功能2: 集中管理异常类型（HMACMismatchError / ReplayDetected / EnqueueError）
  功能3: 标记模块版本与作者
[输入输出]
  输入: 无（仅导出）
  输出: 包级符号（WebHookApp, HMACVerifier, GitHubVerifier, ReplayGuard, Enqueuer, 异常类）
[依赖关系]
  依赖文件: app.py / verifiers/* / replay_guard.py / enqueuer.py / exceptions.py
  被依赖文件: M-D02 (启动装载 metrics 端点) / 部署入口 webhook.runner
[注意事项]
  注意1: 禁止在此文件中编写业务逻辑
  注意2: 公共 API 需在 __all__ 中显式声明，避免通配符导出
[代码风格] 遵循CS-MCP-V1.0（来自DD-001）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本（仅注释与导出声明）
[作者] DD-M-A03-20260603
[来源标注] [DD-001:FS-003]
"""

from __future__ import annotations

from agenthub.access.webhook.app import WebhookApp
from agenthub.access.webhook.enqueuer import Enqueuer
from agenthub.access.webhook.exceptions import (
    EnqueueError,
    HMACMismatchError,
    ReplayDetected,
    WebhookError,
)
from agenthub.access.webhook.replay_guard import ReplayGuard
from agenthub.access.webhook.verifiers.base import HMACVerifier
from agenthub.access.webhook.verifiers.bitbucket import BitbucketVerifier
from agenthub.access.webhook.verifiers.github import GitHubVerifier
from agenthub.access.webhook.verifiers.gitlab import GitLabVerifier

__all__: list[str] = [
    "WebhookApp",
    "HMACVerifier",
    "GitHubVerifier",
    "GitLabVerifier",
    "BitbucketVerifier",
    "ReplayGuard",
    "Enqueuer",
    "WebhookError",
    "HMACMismatchError",
    "ReplayDetected",
    "EnqueueError",
]

__version__: str = "1.0.0"
