"""DeployService（L3）：部署卡用例编排（P2 §4.2.4 + BDD `B-5-P2-DP01`）。

设计要点：
- 提交：plan.validate() 拦截入参 → 落 queued 记录
- 推进：build() 同步模拟 3 阶段 → 落 ready + preview_url（placeholder）
- 失败：模拟构建错（files 中 entry_file 引用不存在脚本）→ 落 failed
- 删除：软删 → status=deleted

P1 骨架：构建以「同步模拟」实现（无真实 Docker / nginx 拉起），返回
preview_url 为 placeholder URL（`https://agenthub-deploy.com/d1-xxx`，与
SPEC §6.4.4 Then-2 一致）。真实构建/容器拉起留 P2+。

注意：service 不做实际异步推送（WS）；L4 router 在 status 变更后 publish 即可。
这里只做持久化 + 状态机。
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.deploy.deployment import (
    Deployment,
    DeploymentPlan,
    DeploymentStage,
    STAGE_SEQUENCES,
)
from app.domain.deploy.errors import DeployBuildError, DeployNotFoundError
from app.domain.enums import DeploymentStatus, DeploymentTarget
from app.domain.repositories import DeploymentRepository

logger = logging.getLogger(__name__)

_SAFE_FILE_KEY = re.compile(r"^[A-Za-z0-9_./\-]+$")


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
        """软删：status=DELETED（保留审计记录）。"""
        d = await self._repo.get_by_id(deployment_id)
        if d is None:
            raise DeployNotFoundError(f"deployment {deployment_id} 不存在")
        if d.status == DeploymentStatus.DELETED:
            return  # 幂等
        d.mark_deleted()
        await self._repo.save(d)

    # --- 内部：同步推进（P1 骨架；真实异步构建留 P2+）---

    async def _advance_synchronous(self, deployment: Deployment) -> None:
        """同步推进：queued → building → ready（或 failed）。

        失败触发条件（per BDD §6.4.4 「失败（构建错）」）：
        - files 中 entry_file 引用了不存在的脚本（grep HTML 找 src/href）
        """
        try:
            deployment.mark_building()
            await self._repo.save(deployment)

            sequence = STAGE_SEQUENCES[deployment.target]
            # 跳过最后一项（READY = 终态阶段）
            mid_stages = sequence[:-1]
            for stage in mid_stages:
                log_line = f"[{stage.value}] {deployment.id}"
                deployment.advance_stage(stage, log=log_line)

                # 容器化：uploading/building 阶段检查构建错误
                if deployment.target == DeploymentTarget.STATIC_SITE:
                    if stage == DeploymentStage.BUILDING:
                        self._check_static_site_build_errors(deployment)

                # 简单进度：每个 stage 追加进度
                await self._repo.save(deployment)

            # 终态：ready
            preview_url = self._build_preview_url(deployment)
            download_url: str | None = None
            if deployment.target == DeploymentTarget.PACKAGE:
                download_url = f"https://agenthub-deploy.com/d{deployment.id.hex[:8]}.zip"
            deployment.mark_ready(preview_url=preview_url, download_url=download_url)
            await self._repo.save(deployment)
        except DeployBuildError as exc:
            logger.warning("部署构建失败 %s: %s", deployment.id, exc)
            deployment.mark_failed(code=exc.code, message=str(exc))
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

    def _build_preview_url(self, deployment: Deployment) -> str:
        """生成 preview_url（placeholder）。"""
        return f"https://agenthub-deploy.com/d{deployment.id.hex[:8]}-{deployment.target.value}"
