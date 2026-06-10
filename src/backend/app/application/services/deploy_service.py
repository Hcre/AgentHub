"""DeployService（L3）：部署卡用例编排（P2 §4.2.4 + BDD `B-5-P2-DP01`）。

设计要点：
- 提交：plan.validate() 拦截入参 → 落 queued 记录
- 推进：build() 推进阶段 → **真实落盘** → 落 ready + 真实可访问 URL
- 失败：构建错（files 中 entry_file 引用不存在脚本）/ 落盘错 / 容器未支持 → 落 failed
- 删除：软删 → status=deleted（同时清盘部署产物）

真实托管（2026-06-10 由 placeholder 假 URL 升级）：
- static_site：files 原样写到 `{deploy_root}/{id}/`，preview_url 指向 FastAPI
  StaticFiles 挂载点 `{public_base_url}/preview/{id}/{entry_file}`，浏览器可真实打开。
- package：files 打成 `{id}/site.zip`，download_url 指向同一挂载点（真实可下载）。
- container：宿主无 Docker 守护进程 → 诚实标记 `E_DEPLOY_CONTAINER_UNSUPPORTED`，
  不再发假 URL（真实容器化留平台化阶段）。

注意：service 不做实际异步 WS 推送；L4 router 在 status 变更后 publish 即可。
落盘 IO 经 `asyncio.to_thread` 包裹，避免阻塞事件循环（CR-12）。
"""

from __future__ import annotations

import asyncio
import logging
import re
from uuid import UUID

from app.core.config import settings
from app.domain.deploy.deployment import (
    STAGE_SEQUENCES,
    Deployment,
    DeploymentPlan,
    DeploymentStage,
)
from app.domain.deploy.errors import DeployBuildError, DeployNotFoundError
from app.domain.enums import DeploymentStatus, DeploymentTarget
from app.domain.repositories import DeploymentRepository
from app.infrastructure.deploy.static_host import DeployStaticError, StaticHost

logger = logging.getLogger(__name__)

_SAFE_FILE_KEY = re.compile(r"^[A-Za-z0-9_./\-]+$")


class DeployService:
    def __init__(
        self, repo: DeploymentRepository, static_host: StaticHost | None = None
    ) -> None:
        self._repo = repo
        # 默认从配置构造（生产路径）；测试可注入指向 tmp 的 StaticHost。
        self._static = static_host or StaticHost(
            settings.deploy_root_path, settings.public_base_url
        )

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
        """创建部署记录（P2 BDD When-1/3/4）。

        1. 构造 DeploymentPlan → validate()（业务规则）
        2. 创建 Deployment（status=queued）
        3. 持久化
        4. **同步推进**到 building → ready（模拟构建），便于 GET 时直接看到 ready
           或 failed 终态
        5. 返回最终实体
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
        await self._advance_synchronous(deployment)
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
        """软删：status=DELETED（保留审计记录）+ 清盘部署产物。"""
        d = await self._repo.get_by_id(deployment_id)
        if d is None:
            raise DeployNotFoundError(f"deployment {deployment_id} 不存在")
        if d.status == DeploymentStatus.DELETED:
            return  # 幂等
        d.mark_deleted()
        await self._repo.save(d)
        # 软删 status 后清盘真实产物（best-effort，失败不影响软删）
        await asyncio.to_thread(self._static.remove, deployment_id)

    # --- 内部：同步推进（P1 骨架；真实异步构建留 P2+）---

    async def _advance_synchronous(self, deployment: Deployment) -> None:
        """推进：queued → building →（真实落盘）→ ready（或 failed）。

        失败触发条件：
        - static_site：files 中 entry_file 引用了不存在的脚本（grep HTML 找 src/href）
        - container：宿主无 Docker → E_DEPLOY_CONTAINER_UNSUPPORTED（诚实拒绝，不发假 URL）
        - 落盘失败（非法路径等）→ E_DEPLOY_HOST_WRITE
        """
        try:
            deployment.mark_building()
            await self._repo.save(deployment)

            target = deployment.target

            # 容器化：当前环境无宿主 Docker 守护进程，诚实拒绝（避免发假 URL）
            if target == DeploymentTarget.CONTAINER:
                raise DeployBuildError(
                    "容器化部署需要宿主 Docker 守护进程，当前环境未启用（请改用静态站点或源码打包）",
                    code="E_DEPLOY_CONTAINER_UNSUPPORTED",
                )

            sequence = STAGE_SEQUENCES[target]
            # 跳过最后一项（READY = 终态阶段，由 mark_ready 设置）
            mid_stages = sequence[:-1]
            for stage in mid_stages:
                deployment.advance_stage(stage, log=f"[{stage.value}] {deployment.id}")
                # 静态站点：building 阶段校验资源引用完整性
                if target == DeploymentTarget.STATIC_SITE and stage == DeploymentStage.BUILDING:
                    self._check_static_site_build_errors(deployment)
                await self._repo.save(deployment)

            # 真实落盘 + 生成可访问 URL
            files = deployment.plan.files
            preview_url: str | None = None
            download_url: str | None = None
            if target == DeploymentTarget.STATIC_SITE:
                entry = deployment.plan.entry_file or "index.html"
                written = await asyncio.to_thread(
                    self._static.write_site, deployment.id, files
                )
                preview_url = self._static.site_url(deployment.id, entry)
                deployment.append_log(f"[host] 写入 {written} 个文件 → {preview_url}")
            elif target == DeploymentTarget.PACKAGE:
                await asyncio.to_thread(self._static.write_zip, deployment.id, files)
                download_url = self._static.download_url(deployment.id)
                deployment.append_log(f"[package] 打包 {len(files)} 个文件 → {download_url}")

            deployment.mark_ready(preview_url=preview_url, download_url=download_url)
            await self._repo.save(deployment)
        except DeployBuildError as exc:
            logger.warning("部署构建失败 %s: %s", deployment.id, exc)
            deployment.mark_failed(code=exc.code, message=str(exc))
            await self._repo.save(deployment)
        except DeployStaticError as exc:
            logger.warning("部署落盘失败 %s: %s", deployment.id, exc)
            deployment.mark_failed(code="E_DEPLOY_HOST_WRITE", message=str(exc))
            await self._repo.save(deployment)
        except Exception as exc:  # 兜底：未预期异常 → failed 而非崩溃
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
        # 提取 src="x.js" / href='x.css'
        refs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', content)
        for ref in refs:
            # 只校验相对路径（http(s):// 视为外链，跳过）
            if ref.startswith(("http://", "https://", "//", "data:")):
                continue
            if ref not in deployment.plan.files:
                raise DeployBuildError(
                    f"构建失败：{entry} 引用了不存在的脚本 {ref}",
                    code="E_DEPLOY_BUILD_MISSING_ASSET",
                )
