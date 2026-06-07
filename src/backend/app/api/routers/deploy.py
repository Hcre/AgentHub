"""Deploy 路由（/api/deployments，P2 §4.2.4 + BDD `B-5-P2-DP01`）。

REST 端点（AP-01 kebab + AP-02 `{error:{code,message}}`）：
- POST   /api/deployments      提交部署（start）
- GET    /api/deployments/{id}  查部署（含 build_logs + preview_url + progress）
- DELETE /api/deployments/{id}  软删（status=deleted）
- GET    /api/deployments      列部署（query: session_id）

SPEC §6.4.4 BDD Then-1/2/3/4 覆盖：
- 静态站点（target=static_site）：queued → building → ready + preview_url
- 容器化（target=container）：5min 超时 → 504 E_DEPLOY_TIMEOUT（P1 骨架同步推进，
  不真超时；保留错误码占位）
- 源码打包（target=package）：返回 download_url
- 失败（构建错）：build_logs 报错 + status=failed

WS 推送（per B-5-P2-DP01 Then-1）：`{type:"deployment:progress", payload:{...}}`
本期 P1 骨架不接 WS，service 同步推进后 GET 即得终态；P2+ 可加 event_bus publish。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_deploy_service
from app.application.services import DeployService
from app.domain.enums import DeploymentTarget
from app.schemas.deploy import DeploymentOut, DeploymentStartRequest

router = APIRouter(prefix="/api/deployments", tags=["deployments"])

ServiceDep = Annotated[DeployService, Depends(get_deploy_service)]


def _to_out(deployment) -> DeploymentOut:  # type: ignore[no-untyped-def]
    """domain Deployment → response DTO。"""
    return DeploymentOut(
        id=deployment.id,
        session_id=deployment.session_id,
        owner_id=deployment.owner_id,
        target=deployment.target.value,
        entry_file=deployment.plan.entry_file,
        framework=deployment.plan.framework,
        status=deployment.status.value,
        stage=deployment.stage.value if deployment.stage else None,
        progress=deployment.progress,
        preview_url=deployment.preview_url,
        download_url=deployment.download_url,
        build_logs=list(deployment.build_logs),
        error_code=deployment.error_code,
        error_message=deployment.error_message,
        ttl=deployment.ttl,
        created_at=deployment.created_at.isoformat(),
        updated_at=deployment.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_deployment(body: DeploymentStartRequest, svc: ServiceDep) -> DeploymentOut:
    """提交部署（start，BDD B-5-P2-DP01 When-1/3/4）。"""
    deployment = await svc.start(
        session_id=body.session_id,
        target=DeploymentTarget(body.target),
        entry_file=body.entry_file,
        framework=body.framework,
        files=body.files,
    )
    return _to_out(deployment)


@router.get("", response_model=list[DeploymentOut])
async def list_deployments(
    svc: ServiceDep,
    session_id: Annotated[UUID, Query(description="按 session 过滤部署")],
    include_deleted: Annotated[bool, Query()] = False,
) -> list[DeploymentOut]:
    """列部署（按 session）。"""
    items = await svc.list_by_session(session_id, include_deleted=include_deleted)
    return [_to_out(d) for d in items]


@router.get("/{deployment_id}", response_model=DeploymentOut)
async def get_deployment(deployment_id: UUID, svc: ServiceDep) -> DeploymentOut:
    """查单个部署（轮询用，BDD Then-2）。"""
    deployment = await svc.get(deployment_id)
    return _to_out(deployment)


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(deployment_id: UUID, svc: ServiceDep) -> Response:
    """软删部署（BDD When-5）。"""
    await svc.delete(deployment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
