"""PostgresGroupRepository：GroupRepository 的 SQLAlchemy 实现。

成员表 group_members 只存人选成员（不含协调者，协调者由 groups.coordinator_id 唯一标识）。
save 时整组重置成员（去重），适配创建场景；更新成员为后续接口。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.group import Group
from app.domain.repositories import GroupRepository
from app.infrastructure.db.models import GroupMemberModel, GroupModel


def _to_domain(m: GroupModel, member_ids: list[UUID]) -> Group:
    return Group(
        id=m.id,
        name=m.name,
        description=m.description,
        coordinator_id=m.coordinator_id,
        coordinator_config=dict(m.coordinator_config or {}),
        member_ids=member_ids,
        workspace_path=m.workspace_path or "",
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_model(g: Group) -> GroupModel:
    return GroupModel(
        id=g.id,
        name=g.name,
        description=g.description,
        coordinator_id=g.coordinator_id,
        coordinator_config=g.coordinator_config,
        workspace_path=g.workspace_path,
    )


def _update_model(m: GroupModel, g: Group) -> None:
    m.name = g.name
    m.description = g.description
    m.coordinator_config = g.coordinator_config
    m.workspace_path = g.workspace_path


class PostgresGroupRepository(GroupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, group: Group) -> None:
        existing = await self._s.get(GroupModel, group.id)
        if existing is None:
            self._s.add(_to_model(group))
        else:
            _update_model(existing, group)
            await self._s.execute(
                delete(GroupMemberModel).where(GroupMemberModel.group_id == group.id)
            )
        await self._s.flush()
        for agent_id in dict.fromkeys(group.member_ids):
            self._s.add(GroupMemberModel(group_id=group.id, agent_id=agent_id))
        await self._s.flush()

    async def get_by_id(self, group_id: UUID) -> Group | None:
        m = await self._s.get(GroupModel, group_id)
        if m is None:
            return None
        return _to_domain(m, await self._member_ids(group_id))

    async def exists_by_name(self, name: str, exclude_id: UUID | None = None) -> bool:
        stmt = select(GroupModel.id).where(GroupModel.name == name)
        if exclude_id is not None:
            stmt = stmt.where(GroupModel.id != exclude_id)
        return (await self._s.execute(stmt)).first() is not None

    async def update_name(self, group_id: UUID, name: str) -> Group | None:
        m = await self._s.get(GroupModel, group_id)
        if m is None:
            return None
        m.name = name
        await self._s.flush()
        return _to_domain(m, await self._member_ids(group_id))

    async def delete(self, group_id: UUID) -> None:
        m = await self._s.get(GroupModel, group_id)
        if m is not None:
            await self._s.delete(m)
            await self._s.flush()

    async def list(self) -> list[Group]:
        rows = (await self._s.execute(select(GroupModel))).scalars().all()
        return [_to_domain(m, await self._member_ids(m.id)) for m in rows]

    async def _member_ids(self, group_id: UUID) -> list[UUID]:
        stmt = select(GroupMemberModel.agent_id).where(GroupMemberModel.group_id == group_id)
        return [row[0] for row in (await self._s.execute(stmt)).all()]
