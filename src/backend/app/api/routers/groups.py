"""群组路由（设计文档 §四）。创建群组自动生成协调者 + 写成员。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_group_service
from app.application.commands import (
    CreateGroupCommand,
    DeleteGroupCommand,
    RenameGroupCommand,
)
from app.application.dto import GroupResponse
from app.application.services import GroupService
from app.schemas.group import (
    GroupCoordinatorOut,
    GroupCreateRequest,
    GroupMemberOut,
    GroupOut,
    GroupRenameRequest,
    NameCheckOut,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])

ServiceDep = Annotated[GroupService, Depends(get_group_service)]


def _to_out(resp: GroupResponse) -> GroupOut:
    return GroupOut(
        id=resp.id,
        name=resp.name,
        description=resp.description,
        coordinator=GroupCoordinatorOut(**resp.coordinator.__dict__),
        members=[GroupMemberOut(**m.__dict__) for m in resp.members],
        created_at=resp.created_at,
    )


@router.get("/check-name", response_model=NameCheckOut)
async def check_name(name: str, svc: ServiceDep) -> NameCheckOut:
    available, reason = await svc.check_name(name)
    return NameCheckOut(available=available, reason=reason)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreateRequest, svc: ServiceDep) -> GroupOut:
    resp = await svc.create(
        CreateGroupCommand(
            name=body.name,
            description=body.description,
            member_ids=body.member_ids,
        )
    )
    return _to_out(resp)


@router.get("", response_model=list[GroupOut])
async def list_groups(svc: ServiceDep) -> list[GroupOut]:
    return [_to_out(r) for r in await svc.list()]


@router.patch("/{group_id}", response_model=GroupOut)
async def rename_group(group_id: UUID, body: GroupRenameRequest, svc: ServiceDep) -> GroupOut:
    return _to_out(await svc.rename(RenameGroupCommand(group_id=group_id, name=body.name)))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: UUID, svc: ServiceDep):
    await svc.delete(DeleteGroupCommand(group_id=group_id))
