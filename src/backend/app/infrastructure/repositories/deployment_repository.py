"""PostgresDeploymentRepository：DeploymentRepository 的 SQLAlchemy 实现。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.deploy.deployment import Deployment, DeploymentPlan
from app.domain.deploy.errors import DeployValidationError
from app.domain.enums import DeploymentStatus, DeploymentTarget
from app.domain.repositories.deployment_repository import DeploymentRepository
from app.infrastructure.db.models import DeploymentModel


def _to_domain(m: DeploymentModel) -> Deployment:
    """ORM 行 → 领域实体（重建 DeploymentPlan + 校验）。"""
    plan = DeploymentPlan(
        session_id=m.session_id,
        target=DeploymentTarget(m.target),
        entry_file=m.entry_file,
        framework=m.framework,
        # files 不持久化（deploy 完成后无意义；plan.validate 允许 files 为空时抛错
        # 但本仓库行是已 validated 后的状态，不再回填校验）
        files={},
    )
    # 跳过 plan.validate：files=空是 OK（重建时只读，校验已在 create 时完成）
    # 但 __post_init__ 会调 validate，需绕开
    obj = Deployment.__new__(Deployment)
    obj.id = m.id
    obj.session_id = m.session_id
    obj.target = plan.target
    obj.plan = plan
    obj.status = DeploymentStatus(m.status)
    obj.progress = m.progress
    obj.stage = None  # stage 不持久化（仅作 WS 推送瞬时值）
    obj.preview_url = m.preview_url
    obj.download_url = m.download_url
    obj.build_logs = list(m.build_logs or [])
    obj.error_code = m.error_code
    obj.error_message = m.error_message
    obj.ttl = m.ttl
    obj.owner_id = m.owner_id
    obj.created_at = m.created_at
    obj.updated_at = m.updated_at
    return obj


def _to_model(d: Deployment) -> DeploymentModel:
    return DeploymentModel(
        id=d.id,
        session_id=d.session_id,
        owner_id=d.owner_id,
        target=d.target.value,
        entry_file=d.plan.entry_file,
        framework=d.plan.framework,
        status=d.status.value,
        stage=d.stage.value if d.stage else None,
        progress=d.progress,
        preview_url=d.preview_url,
        download_url=d.download_url,
        build_logs=list(d.build_logs),
        error_code=d.error_code,
        error_message=d.error_message,
        ttl=d.ttl,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


class PostgresDeploymentRepository(DeploymentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, deployment: Deployment) -> None:
        existing = await self._s.get(DeploymentModel, deployment.id)
        if existing is None:
            self._s.add(_to_model(deployment))
        else:
            m = existing
            m.target = deployment.target.value
            m.entry_file = deployment.plan.entry_file
            m.framework = deployment.plan.framework
            m.status = deployment.status.value
            m.stage = deployment.stage.value if deployment.stage else None
            m.progress = deployment.progress
            m.preview_url = deployment.preview_url
            m.download_url = deployment.download_url
            m.build_logs = list(deployment.build_logs)
            m.error_code = deployment.error_code
            m.error_message = deployment.error_message
            m.ttl = deployment.ttl
            m.updated_at = deployment.updated_at
        await self._s.flush()

    async def get_by_id(self, deployment_id: UUID) -> Deployment | None:
        m = await self._s.get(DeploymentModel, deployment_id)
        if m is None:
            return None
        return _to_domain(m)

    async def list_by_session(
        self, session_id: UUID, *, include_deleted: bool = False
    ) -> list[Deployment]:
        stmt = select(DeploymentModel).where(DeploymentModel.session_id == session_id)
        if not include_deleted:
            stmt = stmt.where(DeploymentModel.status != DeploymentStatus.DELETED.value)
        stmt = stmt.order_by(DeploymentModel.created_at.desc())
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]
