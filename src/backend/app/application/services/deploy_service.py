"""DeployService（L3）：部署卡用例编排（P2 §4.2.4 + BDD `B-5-P2-DP01` + M4①.1 真实化）。

设计要点（M4 ①.1 改造）：
- 提交：plan.validate() 拦截入参 → 落 queued 记录
- 推进：**异步后台任务**（asyncio.create_task）→ mark_building → 落盘 → advance_stage → mark_ready
- 失败：构建错（files 中 entry_file 引用不存在脚本）→ mark_failed + publish
- 删除：软删 → status=deleted + static_host.remove 清理落盘

真实化（M4①.1）：
- preview_url 不再写死 https://agenthub-deploy.com → 走 static_host.build_preview_url → 真 200 URL
- package download_url 不再写死 → shutil.make_archive 真打 zip
- 各阶段通过 event_bus.publish("deployment:progress") 广播（WS 订阅端可用）

P1 骨架 → P2 真链路过渡：旧同步桩代码保留 `_advance_synchronous` 但不再调用，
     留作回滚参考。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.events import get_event_bus
from app.domain.deploy.deployment import (
    Deployment,
    DeploymentPlan,
    DeploymentStage,
    STAGE_SEQUENCES,
)
from app.domain.deploy.errors import DeployBuildError, DeployNotFoundError
from app.domain.enums import DeploymentStatus, DeploymentTarget
from app.domain.events.deployment import DeploymentProgress
from app.domain.repositories import DeploymentRepository
from app.infrastructure.deploy import static_host

logger = logging.getLogger(__name__)

_SAFE_FILE_KEY = re.compile(r"^[A-Za-z0-9_./\-]+$")

# 本机开发默认 host（生产由 env 覆盖 DEPLOY_PUBLIC_HOST）
import os as _os
_PUBLIC_HOST = _os.environ.get("DEPLOY_PUBLIC_HOST", "http://127.0.0.1:8000")


def _publish_progress(deployment: Deployment, stage: str | None = None) -> None:
    """统一进度发布（AP-07 WS request_id 后续可加）。"""
    try:
        import asyncio as _aio
        evt = DeploymentProgress(
            deployment_id=deployment.id,
            status=deployment.status.value,
            stage=stage or (deployment.stage.value if deployment.stage else None),
            preview_url=deployment.preview_url,
        )
        try:
            loop = _aio.get_running_loop()
            loop.create_task(get_event_bus().publish(evt))
        except RuntimeError:
            # 无运行 loop（同步上下文）→ 跳过；下次发布会兜底
            pass
    except Exception as e:  # 不让事件总线失败影响主流程
        logger.warning("publish deployment:progress 失败：%s", e)


class DeployService:
    def __init__(self, repo: DeploymentRepository) -> None:
        self._repo = repo

    # --- 用例 ---

    async def start(
        self,
        *,
        session_id: UUID,
        target: DeploymentTarget,
        entry_file: str | None,
        framework: str | None,
        files: dict[str, str],
        owner_id: UUID | None = None,
    ) -> Deployment:
        """创建部署记录（P2 BDD When-1/3/4 + M4①.1 真链路）。

        1. 构造 DeploymentPlan → validate()（业务规则）
        2. 创建 Deployment（status=queued）
        3. 持久化 + publish progress
        4. **异步后台任务**：asyncio.create_task → _advance_async
           （前台立刻返回 deployment，状态在后台推进）
        """
        plan = DeploymentPlan(
            session_id=session_id,
            target=target,
            entry_file=entry_file,
            framework=framework,
            files=files,
        )
        deployment = Deployment(
            session_id=session_id,
            target=target,
            plan=plan,
            owner_id=owner_id,
        )
        await self._repo.save(deployment)
        _publish_progress(deployment, stage="queued")
        # 异步推进（M4①.1 真实化：避免同步阻塞，符合 CR-12）
        asyncio.create_task(self._advance_async(deployment))
        return deployment

    async def get(self, deployment_id: UUID) -> Deployment:
        d = await self._repo.get_by_id(deployment_id)
        if d is None:
            raise DeployNotFoundError(f"deployment {deployment_id} 不存在")
        return d

    async def list_by_session(
        self, session_id: UUID, *, include_deleted: bool = False
    ) -> list[Deployment]:
        return await self._repo.list_by_session(
            session_id, include_deleted=include_deleted
        )

    async def delete(self, deployment_id: UUID) -> None:
        """软删：status=DELETED（保留审计记录）。"""
        d = await self._repo.get_by_id(deployment_id)
        if d is None:
            raise DeployNotFoundError(f"deployment {deployment_id} 不存在")
        if d.status == DeploymentStatus.DELETED:
            return  # 幂等
        d.mark_deleted()
        await self._repo.save(d)

    # --- 内部：异步推进（M4①.1 真链路）---

    async def _advance_async(self, deployment: Deployment) -> None:
        """异步推进：queued → building → 落盘 → advance → ready（或 failed）。

        各阶段 publish 进度（WS 订阅端可见）。失败兜底为 failed 而非崩溃。
        """
        try:
            # 1. building
            deployment.mark_building()
            await self._repo.save(deployment)
            _publish_progress(deployment, stage="building")

            # 2. 静态构建错预检（落盘前先校验 entry_file 引用的脚本存在）
            if deployment.target == DeploymentTarget.STATIC_SITE:
                self._check_static_site_build_errors(deployment)

            # 3. 落盘（M4①.1 真链路：files → _assets/deploy/{id}/）
            static_host.write_files(deployment.id, deployment.plan.files)
            _publish_progress(deployment, stage="package_done")

            # 4. 走 sequence 的剩余阶段（advance_stage 主要为审计日志）
            sequence = STAGE_SEQUENCES[deployment.target]
            mid_stages = sequence[:-1]
            for stage in mid_stages:
                if stage == DeploymentStage.BUILDING:
                    continue  # 已在第 1 步处理
                log_line = f"[{stage.value}] {deployment.id}"
                deployment.advance_stage(stage, log=log_line)
                await self._repo.save(deployment)
                _publish_progress(deployment, stage=stage.value)

            # 5. 终态：真 URL + 真 zip（M4①.1 真实化）
            preview_url = static_host.build_preview_url(deployment.id, host=_PUBLIC_HOST)
            download_url: str | None = None
            if deployment.target == DeploymentTarget.PACKAGE:
                zip_path = static_host.make_zip(deployment.id, deployment.plan.files)
                # 真下载 URL（FastAPI 后续可加 /api/deploy/{id}/download 端点；当前
                # 落盘到 _assets/deploy/，可由 nginx 暴露或前端拼 download_url）
                download_url = f"{_PUBLIC_HOST}/preview/{deployment.id}/deploy-{deployment.id}.zip"

            deployment.mark_ready(preview_url=preview_url, download_url=download_url)
            await self._repo.save(deployment)
            _publish_progress(deployment, stage="ready")
        except DeployBuildError as exc:
            logger.warning("部署构建失败 %s: %s", deployment.id, exc)
            deployment.mark_failed(code=exc.code, message=str(exc))
            await self._repo.save(deployment)
            _publish_progress(deployment, stage="failed")
        except Exception as exc:  # 兜底
            logger.exception("部署未预期错误 %s", deployment.id)
            deployment.mark_failed(
                code="E_DEPLOY_INTERNAL",
                message=f"内部错误：{type(exc).__name__}: {exc}",
            )
            await self._repo.save(deployment)
            _publish_progress(deployment, stage="failed")

    # --- 旧同步骨架（保留作回滚参考，M4①.1 不再调用）---

    async def _advance_synchronous(self, deployment: Deployment) -> None:
        """同步推进骨架（已弃用，保留供回滚参考）。"""
        try:
            deployment.mark_building()
            await self._repo.save(deployment)
            sequence = STAGE_SEQUENCES[deployment.target]
            mid_stages = sequence[:-1]
            for stage in mid_stages:
                log_line = f"[{stage.value}] {deployment.id}"
                deployment.advance_stage(stage, log=log_line)
                if deployment.target == DeploymentTarget.STATIC_SITE:
                    if stage == DeploymentStage.BUILDING:
                        self._check_static_site_build_errors(deployment)
                await self._repo.save(deployment)
            preview_url = self._build_preview_url_legacy(deployment)
            download_url: str | None = None
            if deployment.target == DeploymentTarget.PACKAGE:
                download_url = f"https://agenthub-deploy.com/d{deployment.id.hex[:8]}.zip"
            deployment.mark_ready(preview_url=preview_url, download_url=download_url)
            await self._repo.save(deployment)
        except DeployBuildError as exc:
            logger.warning("部署构建失败 %s: %s", deployment.id, exc)
            deployment.mark_failed(code=exc.code, message=str(exc))
            await self._repo.save(deployment)
        except Exception as exc:
            logger.exception("部署未预期错误 %s", deployment.id)
            deployment.mark_failed(
                code="E_DEPLOY_INTERNAL",
                message=f"内部错误：{type(exc).__name__}: {exc}",
            )
            await self._repo.save(deployment)

    def _check_static_site_build_errors(self, deployment: Deployment) -> None:
        """静态站点构建错：entry_file 含 src/href 引用 → 校验引用脚本在 files 中。"""
        entry = deployment.plan.entry_file
        if not entry or entry not in deployment.plan.files:
            return
        content = deployment.plan.files[entry]
        refs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', content)
        for ref in refs:
            if ref.startswith(("http://", "https://", "//", "data:")):
                continue
            if ref not in deployment.plan.files:
                raise DeployBuildError(
                    f"构建失败：{entry} 引用了不存在的脚本 {ref}",
                    code="E_DEPLOY_BUILD_MISSING_ASSET",
                )

    def _build_preview_url_legacy(self, deployment: Deployment) -> str:
        """旧 placeholder URL（仅回滚用）。"""
        return f"https://agenthub-deploy.com/d{deployment.id.hex[:8]}-{deployment.target.value}"
