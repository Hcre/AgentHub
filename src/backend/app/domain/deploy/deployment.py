"""Deployment 聚合根 + 状态机 + Plan 值对象（P2 部署卡 B-5-P2-DP01）。

状态机：
    queued → building → ready
                      ↘ failed
    ready/failed → deleted（DELETE 端点软删；非物理删除，保留审计）

阶段（stage，用于进度条 + WS 推送 `deployment:progress`）：
    静态站点：uploading → building → ready
    容器化：  building_image → pushing → starting → running
    源码打包：uploading → packaging → ready

设计依据：
- docs/specs/04-commands §6.4.4 B-5-P2-DP01（5 When/Then + 边界）
- docs/specs/01-architecture §3.2 协调者降级路径（per ADR 矩阵）
- AR-05：领域实体不依赖上层；状态转换仅通过 transition_deployment()
- 任务描述：deploy card status state machine (queued → building → ready → failed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.domain.deploy.errors import (
    DeployInvalidStageError,
    DeployInvalidTransitionError,
    DeployValidationError,
)
from app.domain.enums import DeploymentStatus, DeploymentTarget


def _now() -> datetime:
    return datetime.now(UTC)


class DeploymentStage(StrEnum):
    """部署阶段（与 status 配合，stage 决定 WS 推送内容）。

    注意：`stage` 是 **进度事件**（一次部署可多次推送 stage 变更），
    `status` 是 **终态判定**（决定部署卡显示 ✅/❌）。
    """

    UPLOADING = "uploading"
    BUILDING = "building"
    BUILDING_IMAGE = "building_image"
    PUSHING = "pushing"
    STARTING = "starting"
    RUNNING = "running"
    PACKAGING = "packaging"
    READY = "ready"
    FAILED = "failed"


# 合法流转表（per B-5-P2-DP01 §When-1/3/4）
VALID_DEPLOYMENT_TRANSITIONS: dict[DeploymentStatus, set[DeploymentStatus]] = {
    DeploymentStatus.QUEUED: {DeploymentStatus.BUILDING, DeploymentStatus.FAILED},
    DeploymentStatus.BUILDING: {DeploymentStatus.READY, DeploymentStatus.FAILED},
    DeploymentStatus.READY: {DeploymentStatus.DELETED},
    DeploymentStatus.FAILED: {DeploymentStatus.DELETED},
    DeploymentStatus.DELETED: set(),  # 终态（软删后不再变化）
}

TERMINAL_DEPLOYMENT_STATUSES: set[DeploymentStatus] = {
    DeploymentStatus.READY,
    DeploymentStatus.FAILED,
    DeploymentStatus.DELETED,
}


def is_terminal_deployment_status(status: DeploymentStatus) -> bool:
    """是否终态（ready/failed/deleted，不再流转 status）。"""
    return status in TERMINAL_DEPLOYMENT_STATUSES


def transition_deployment(
    current: DeploymentStatus, target: DeploymentStatus
) -> None:
    """校验状态流转合法性；非法 → DeployInvalidTransitionError。

    AR-05 风格：所有 status 变更必须经过本函数（不直接赋值 status）。
    """
    if target not in VALID_DEPLOYMENT_TRANSITIONS.get(current, set()):
        raise DeployInvalidTransitionError(
            f"非法状态转换：{current.value} → {target.value}"
        )


# target → 阶段序列
STAGE_SEQUENCES: dict[DeploymentTarget, list[DeploymentStage]] = {
    DeploymentTarget.STATIC_SITE: [
        DeploymentStage.UPLOADING,
        DeploymentStage.BUILDING,
        DeploymentStage.READY,
    ],
    DeploymentTarget.CONTAINER: [
        DeploymentStage.BUILDING_IMAGE,
        DeploymentStage.PUSHING,
        DeploymentStage.STARTING,
        DeploymentStage.RUNNING,
    ],
    DeploymentTarget.PACKAGE: [
        DeploymentStage.UPLOADING,
        DeploymentStage.PACKAGING,
        DeploymentStage.READY,
    ],
}


@dataclass
class DeploymentPlan:
    """部署计划值对象（前端入参 → L3 service 包装）。

    字段对齐 B-5-P2-DP01 When-1/3/4：
    - session_id: 来源会话（关联 S1 私聊 / S2 群聊）
    - target: 部署目标类型
    - entry_file: 入口文件（static_site 必填；package 可选）
    - framework: 框架提示（container 时如 docker / node / python）
    - files: 文件清单（dict: 相对路径 → 内容字符串；静态站点直接 zip）
    """

    session_id: UUID
    target: DeploymentTarget
    entry_file: str | None = None
    framework: str | None = None
    files: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """业务规则校验（不依赖 L1 仓储）。

        规则：
        - static_site 必须提供 entry_file
        - container 推荐 framework（缺失 → warning，不阻断）
        - files 不能为空
        - entry_file 必须在 files 内
        """
        if not self.files:
            raise DeployValidationError("E_DEPLOY_FILES_EMPTY: 至少上传 1 个文件")
        if self.target == DeploymentTarget.STATIC_SITE:
            if not self.entry_file:
                raise DeployValidationError(
                    "E_DEPLOY_ENTRY_REQUIRED: 静态站点必须指定 entry_file（如 index.html）"
                )
            if self.entry_file not in self.files:
                raise DeployValidationError(
                    f"E_DEPLOY_ENTRY_NOT_FOUND: 入口文件不在 files 中：{self.entry_file}"
                )
        if self.target == DeploymentTarget.CONTAINER and not self.framework:
            # 软警告：L3 service 可写日志，不阻断
            pass


@dataclass
class Deployment:
    """Deployment 聚合根（含 status 状态机 + build_logs + preview_url）。

    字段对齐 B-5-P2-DP01 Then-1/2/3/4：
    - id, status, target, entry_file, framework
    - preview_url / download_url（ready 时回填）
    - build_logs: 阶段日志（list[str]，每条 = 一行 stage 输出）
    - progress: 0.0-1.0（WS 推送用）
    - error_code / error_message: 失败时回填
    - ttl: 过期秒数（默认 3600）
    - created_at / updated_at: 审计
    """

    session_id: UUID
    target: DeploymentTarget
    plan: DeploymentPlan
    status: DeploymentStatus = DeploymentStatus.QUEUED
    progress: float = 0.0
    stage: DeploymentStage | None = None
    preview_url: str | None = None
    download_url: str | None = None
    build_logs: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    ttl: int = 3600
    id: UUID = field(default_factory=uuid4)
    owner_id: UUID | None = None  # R2：JWT sub，裸 UUID 无 FK
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.plan.validate()

    # --- 状态机操作（AR-05 风格：所有变更走 transition_deployment）---

    def mark_building(self) -> None:
        """queued → building。"""
        transition_deployment(self.status, DeploymentStatus.BUILDING)
        self.status = DeploymentStatus.BUILDING
        self.stage = STAGE_SEQUENCES[self.target][0]
        self.progress = 0.1
        self.updated_at = _now()

    def advance_stage(self, stage: DeploymentStage, *, log: str | None = None) -> None:
        """推进到下一阶段（building 中）。stage 必须在 STAGE_SEQUENCES 内。"""
        if stage not in STAGE_SEQUENCES[self.target]:
            raise DeployInvalidStageError(
                f"E_DEPLOY_STAGE_INVALID: 目标 {self.target.value} 不支持阶段 {stage.value}"
            )
        if self.status != DeploymentStatus.BUILDING:
            raise DeployInvalidTransitionError(
                f"仅 building 状态可推进阶段，当前：{self.status.value}"
            )
        self.stage = stage
        sequence = STAGE_SEQUENCES[self.target]
        idx = sequence.index(stage)
        self.progress = round((idx + 1) / len(sequence), 2)
        if log:
            self.build_logs.append(log)
        self.updated_at = _now()

    def append_log(self, log: str) -> None:
        """追加构建日志（任意中间状态可调）。"""
        self.build_logs.append(log)
        self.updated_at = _now()

    def mark_ready(self, *, preview_url: str | None = None, download_url: str | None = None) -> None:
        """building → ready。"""
        transition_deployment(self.status, DeploymentStatus.READY)
        self.status = DeploymentStatus.READY
        self.stage = DeploymentStage.READY
        self.progress = 1.0
        if preview_url:
            self.preview_url = preview_url
        if download_url:
            self.download_url = download_url
        self.updated_at = _now()

    def mark_failed(self, *, code: str, message: str) -> None:
        """queued/building → failed。终态。"""
        transition_deployment(self.status, DeploymentStatus.FAILED)
        self.status = DeploymentStatus.FAILED
        self.stage = DeploymentStage.FAILED
        self.error_code = code
        self.error_message = message
        self.build_logs.append(f"[ERROR] {code}: {message}")
        self.updated_at = _now()

    def mark_deleted(self) -> None:
        """ready/failed → deleted（软删）。终态。"""
        transition_deployment(self.status, DeploymentStatus.DELETED)
        self.status = DeploymentStatus.DELETED
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（响应体 / DB 行）。"""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "owner_id": str(self.owner_id) if self.owner_id else None,
            "target": self.target.value,
            "entry_file": self.entry_file,
            "framework": self.framework,
            "status": self.status.value,
            "stage": self.stage.value if self.stage else None,
            "progress": self.progress,
            "preview_url": self.preview_url,
            "download_url": self.download_url,
            "build_logs": list(self.build_logs),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "ttl": self.ttl,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
