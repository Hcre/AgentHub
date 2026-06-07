"""Deploy P2 测试（L3 service + L1 repo + 状态机）。

覆盖三路径（T-03）：正常 / 异常 / 边界。
- 路径 1：start 静态站点（合法 files）→ 推进到 ready + preview_url
- 路径 2：start 源码打包 → ready + download_url（不返 preview_url）
- 路径 3：start 静态站点（缺 entry_file 或 entry_file 引用不存在脚本）→ failed

状态机：mark_building/mark_ready/mark_failed/mark_deleted；非法转换抛错。
domain 规则：DeploymentPlan.validate() 拦截空 files / 缺 entry_file。
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.application.services import DeployService
from app.domain.deploy.deployment import (
    Deployment,
    DeploymentPlan,
    DeploymentStage,
    STAGE_SEQUENCES,
    transition_deployment,
)
from app.domain.deploy.errors import (
    DeployBuildError,
    DeployInvalidTransitionError,
    DeployValidationError,
)
from app.domain.enums import DeploymentStatus, DeploymentTarget
from app.infrastructure.db.models import DeploymentModel
from app.infrastructure.repositories import PostgresDeploymentRepository


def _svc(db):  # type: ignore[no-untyped-def]
    return DeployService(PostgresDeploymentRepository(db))


# ============ 1. domain 规则（无 DB）============


def test_plan_validate_rejects_empty_files() -> None:
    plan = DeploymentPlan(
        session_id=uuid4(),
        target=DeploymentTarget.STATIC_SITE,
        entry_file="index.html",
        files={},
    )
    with pytest.raises(DeployValidationError):
        plan.validate()


def test_plan_validate_rejects_static_site_without_entry() -> None:
    plan = DeploymentPlan(
        session_id=uuid4(),
        target=DeploymentTarget.STATIC_SITE,
        entry_file=None,
        files={"app.js": "//"},
    )
    with pytest.raises(DeployValidationError):
        plan.validate()


def test_plan_validate_rejects_entry_not_in_files() -> None:
    plan = DeploymentPlan(
        session_id=uuid4(),
        target=DeploymentTarget.STATIC_SITE,
        entry_file="index.html",
        files={"app.js": "//"},
    )
    with pytest.raises(DeployValidationError):
        plan.validate()


def test_plan_validate_container_with_no_framework_passes() -> None:
    """container 可缺 framework（软警告，非阻断）。"""
    plan = DeploymentPlan(
        session_id=uuid4(),
        target=DeploymentTarget.CONTAINER,
        framework=None,
        files={"Dockerfile": "FROM scratch"},
    )
    plan.validate()  # 不应抛


def test_transition_illegal_raises() -> None:
    with pytest.raises(DeployInvalidTransitionError):
        transition_deployment(DeploymentStatus.QUEUED, DeploymentStatus.READY)


def test_stage_sequences_target_specific() -> None:
    """3 个 target 阶段序列不同。"""
    assert STAGE_SEQUENCES[DeploymentTarget.STATIC_SITE] == [
        DeploymentStage.UPLOADING,
        DeploymentStage.BUILDING,
        DeploymentStage.READY,
    ]
    assert STAGE_SEQUENCES[DeploymentTarget.CONTAINER][0] == DeploymentStage.BUILDING_IMAGE
    assert STAGE_SEQUENCES[DeploymentTarget.PACKAGE][-1] == DeploymentStage.READY


# ============ 2. 服务：start → ready（静态站点）============


@pytest.mark.asyncio
async def test_start_static_site_reaches_ready_with_preview_url(db_session):  # type: ignore[no-untyped-def]
    """路径 1：合法静态站点 → 同步推进到 ready + preview_url。"""
    svc = _svc(db_session)
    sid = uuid4()
    deployment = await svc.start(
        session_id=sid,
        target=DeploymentTarget.STATIC_SITE,
        entry_file="index.html",
        framework=None,
        files={
            "index.html": "<html><body><script src='app.js'></script></body></html>",
            "app.js": "console.log('hi')",
        },
    )
    assert deployment.status == DeploymentStatus.READY
    assert deployment.progress == 1.0
    assert deployment.preview_url is not None
    assert deployment.preview_url.startswith("https://agenthub-deploy.com/d")
    assert deployment.download_url is None
    assert deployment.error_code is None
    # 持久化校验
    repo = PostgresDeploymentRepository(db_session)
    row = await repo.get_by_id(deployment.id)
    assert row is not None
    assert row.status == "ready"
    # DB 行 build_logs 应非空（每阶段一行）
    assert len(row.build_logs) >= 1


@pytest.mark.asyncio
async def test_start_package_target_returns_download_url(db_session):  # type: ignore[no-untyped-def]
    """路径 2：源码打包 → ready + download_url（不返 preview_url）。"""
    svc = _svc(db_session)
    deployment = await svc.start(
        session_id=uuid4(),
        target=DeploymentTarget.PACKAGE,
        entry_file=None,
        framework=None,
        files={"index.html": "x", "app.js": "y"},
    )
    assert deployment.status == DeploymentStatus.READY
    assert deployment.download_url is not None
    assert deployment.download_url.endswith(".zip")
    assert deployment.preview_url is not None  # placeholder 仍写


# ============ 3. 服务：start → failed（构建错）============


@pytest.mark.asyncio
async def test_start_static_site_missing_asset_fails(db_session):  # type: ignore[no-untyped-def]
    """路径 3：index.html 引用不存在的脚本 → 同步失败。"""
    svc = _svc(db_session)
    deployment = await svc.start(
        session_id=uuid4(),
        target=DeploymentTarget.STATIC_SITE,
        entry_file="index.html",
        framework=None,
        files={
            "index.html": "<html><body><script src='missing.js'></script></body></html>",
        },
    )
    assert deployment.status == DeploymentStatus.FAILED
    assert deployment.error_code == "E_DEPLOY_BUILD_MISSING_ASSET"
    assert "missing.js" in (deployment.error_message or "")
    # build_logs 末行是错误日志
    assert any("E_DEPLOY_BUILD_MISSING_ASSET" in log for log in deployment.build_logs)
    # preview_url 仍为 None（未到 ready）
    assert deployment.preview_url is None


@pytest.mark.asyncio
async def test_start_empty_files_raises_validation(db_session):  # type: ignore[no-untyped-def]
    """边界：files 为空 → plan.validate() 抛错（不创建记录）。"""
    svc = _svc(db_session)
    with pytest.raises(DeployValidationError):
        await svc.start(
            session_id=uuid4(),
            target=DeploymentTarget.STATIC_SITE,
            entry_file="index.html",
            framework=None,
            files={},
        )


# ============ 4. 状态机：get / delete / list ============


@pytest.mark.asyncio
async def test_get_deployment_not_found(db_session):  # type: ignore[no-untyped-def]
    svc = _svc(db_session)
    with pytest.raises(Exception):  # DeployNotFoundError
        await svc.get(uuid4())


@pytest.mark.asyncio
async def test_get_and_delete_deployment(db_session):  # type: ignore[no-untyped-def]
    """get 已创建记录；delete 软删 → status=deleted；二次 delete 幂等。"""
    svc = _svc(db_session)
    sid = uuid4()
    deployment = await svc.start(
        session_id=sid,
        target=DeploymentTarget.PACKAGE,
        entry_file=None,
        framework=None,
        files={"a.txt": "x"},
    )
    fetched = await svc.get(deployment.id)
    assert fetched.id == deployment.id

    # delete → status=deleted
    await svc.delete(deployment.id)
    fetched2 = await svc.get(deployment.id)
    assert fetched2.status == DeploymentStatus.DELETED

    # 二次 delete 幂等
    await svc.delete(deployment.id)
    fetched3 = await svc.get(deployment.id)
    assert fetched3.status == DeploymentStatus.DELETED


@pytest.mark.asyncio
async def test_list_by_session_excludes_deleted(db_session):  # type: ignore[no-untyped-def]
    """list 默认排除 deleted 软删记录。"""
    svc = _svc(db_session)
    sid = uuid4()
    d1 = await svc.start(
        session_id=sid,
        target=DeploymentTarget.PACKAGE,
        entry_file=None,
        framework=None,
        files={"a.txt": "x"},
    )
    d2 = await svc.start(
        session_id=sid,
        target=DeploymentTarget.PACKAGE,
        entry_file=None,
        framework=None,
        files={"b.txt": "y"},
    )
    await svc.delete(d1.id)

    items = await svc.list_by_session(sid)
    assert len(items) == 1
    assert items[0].id == d2.id

    items_all = await svc.list_by_session(sid, include_deleted=True)
    assert len(items_all) == 2


# ============ 5. 实体：mark_deleted 终态 ============


def test_deployment_mark_deleted_only_from_terminal() -> None:
    """mark_deleted 仅从 ready/failed 流转（queued/building 不可直删）。"""
    plan = DeploymentPlan(
        session_id=uuid4(),
        target=DeploymentTarget.PACKAGE,
        files={"x": "y"},
    )
    d = Deployment(
        session_id=plan.session_id,
        target=plan.target,
        plan=plan,
    )
    # queued 状态：直接 mark_deleted 抛错
    with pytest.raises(DeployInvalidTransitionError):
        d.mark_deleted()
    # 推 building
    d.mark_building()
    with pytest.raises(DeployInvalidTransitionError):
        d.mark_deleted()
    # 推 ready → 可删
    d.mark_ready(preview_url="x")
    d.mark_deleted()
    assert d.status == DeploymentStatus.DELETED


def test_deployment_advance_stage_requires_building() -> None:
    plan = DeploymentPlan(
        session_id=uuid4(),
        target=DeploymentTarget.STATIC_SITE,
        entry_file="index.html",
        files={"index.html": "x"},
    )
    d = Deployment(
        session_id=plan.session_id,
        target=plan.target,
        plan=plan,
    )
    # queued 状态 advance_stage 抛错
    with pytest.raises(DeployInvalidTransitionError):
        d.advance_stage(DeploymentStage.UPLOADING)
