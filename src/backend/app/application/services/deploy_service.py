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
import contextlib
import logging
import re
from typing import Any
from uuid import UUID

from app.core.events import get_event_bus
from app.domain.deploy.deployment import (
    STAGE_SEQUENCES,
    Deployment,
    DeploymentPlan,
    DeploymentStage,
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
    def __init__(
        self,
        repo: DeploymentRepository,
        *,
        bg_session_factory: Any = None,
    ) -> None:
        self._repo = repo
        # M4①.1 修复：后台推进任务必须用**独立 session**，不能复用请求作用域
        # 的 session（请求返回即关闭，导致后台 save 失败、部署卡在 queued）。
        # 生产默认开全局 session_factory 新 session；测试可注入复用同一 session 的
        # 工厂以便 _drain_background 同步驱动后断言落库。
        self._bg_session_factory = bg_session_factory
        # 持有后台推进任务的强引用：fire-and-forget 的 create_task 可能被 GC 中途回收
        # （会让部署再次停滞）。存进 set、完成时移除。
        self._bg_tasks: set[asyncio.Task[None]] = set()

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
        task = asyncio.create_task(self._advance_async(deployment))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
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
        """后台推进入口：开**独立 session** 再委托 _run_advance。

        M4①.1 修复关键：请求作用域 session 在 POST 返回后即关闭，原实现复用它
        导致后台首个 save 失败、部署永久卡在 queued。这里改为开新 session（生产
        走全局 session_factory；测试注入复用同一 session 的工厂）。
        """
        if self._bg_session_factory is not None:
            cm = self._bg_session_factory()
        else:
            from app.infrastructure.db.base import session_factory

            cm = session_factory()
        async with cm as db:
            from app.infrastructure.repositories import PostgresDeploymentRepository

            repo = PostgresDeploymentRepository(db)
            await self._run_advance(deployment, repo, db)

    async def _run_advance(self, deployment: Deployment, repo, db) -> None:  # type: ignore[no-untyped-def]
        """推进核心：queued → building → 落盘 → advance → ready（或 failed）。

        每阶段 commit（让 GET 轮询看到中间态）+ publish 进度。失败兜底为 failed。
        """

        async def _save() -> None:
            await repo.save(deployment)
            await db.commit()

        try:
            # 1. building
            deployment.mark_building()
            await _save()
            _publish_progress(deployment, stage="building")

            # 2. 静态构建错预检（落盘前先校验 entry_file 引用的脚本存在）
            if deployment.target == DeploymentTarget.STATIC_SITE:
                self._check_static_site_build_errors(deployment)

            # 3. 落盘（M4①.1 真链路：files → _assets/deploy/{id}/）
            static_host.write_files(deployment.id, deployment.plan.files)
            _publish_progress(deployment, stage="package_done")

            # 4. 走 sequence 的剩余阶段（advance_stage 主要为审计日志）
            sequence = STAGE_SEQUENCES[deployment.target]
            for stage in sequence[:-1]:
                if stage == DeploymentStage.BUILDING:
                    continue  # 已在第 1 步处理
                deployment.advance_stage(stage, log=f"[{stage.value}] {deployment.id}")
                await _save()
                _publish_progress(deployment, stage=stage.value)

            # 5. 终态：真 URL + 真 zip（M4①.1 真实化）
            preview_url = static_host.build_preview_url(deployment.id, host=_PUBLIC_HOST)
            download_url: str | None = None
            if deployment.target == DeploymentTarget.PACKAGE:
                static_host.make_zip(deployment.id, deployment.plan.files)
                download_url = (
                    f"{_PUBLIC_HOST}/preview/{deployment.id}/deploy-{deployment.id}.zip"
                )

            deployment.mark_ready(preview_url=preview_url, download_url=download_url)
            await _save()
            _publish_progress(deployment, stage="ready")
        except DeployBuildError as exc:
            logger.warning("部署构建失败 %s: %s", deployment.id, exc)
            deployment.mark_failed(code=exc.code, message=str(exc))
            await _save()
            _publish_progress(deployment, stage="failed")
        except Exception as exc:  # 兜底
            logger.exception("部署未预期错误 %s", deployment.id)
            deployment.mark_failed(
                code="E_DEPLOY_INTERNAL",
                message=f"内部错误：{type(exc).__name__}: {exc}",
            )
            with contextlib.suppress(Exception):
                await _save()
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
