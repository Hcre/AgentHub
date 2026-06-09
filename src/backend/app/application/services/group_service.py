"""GroupService（L3）：群组创建用例（设计文档 §四）。

创建流程（同一 DB 事务，由 get_session 统一提交）：
1. 校验 name 唯一 → DomainError(409)
2. 去重并校验 member_ids 全部存在 → ValidationError(422)
3. 自动创建协调者 Agent（is_system，mock 运行时，provider=system）
4. 创建 Group（coordinator_id 指向协调者）+ 写 group_members
5. 返回 GroupResponse（含 coordinator + members 详情）
"""

from __future__ import annotations

import asyncio

from app.application.commands import (
    CreateGroupCommand,
    DeleteGroupCommand,
    RenameGroupCommand,
)
from app.application.dto import (
    GroupCoordinatorResponse,
    GroupMemberResponse,
    GroupResponse,
)
from app.core.events import EventBus
from app.core.exceptions import DomainError, NotFoundError, ValidationError
from app.domain.entities.agent import Agent
from app.domain.entities.group import Group
from app.domain.enums import AgentSystem
from app.domain.repositories import AgentRepository, GroupRepository


class GroupService:
    def __init__(
        self,
        group_repo: GroupRepository,
        agent_repo: AgentRepository,
        event_bus: EventBus,
    ) -> None:
        self._groups = group_repo
        self._agents = agent_repo
        self._bus = event_bus

    async def create(self, cmd: CreateGroupCommand) -> GroupResponse:
        if await self._groups.exists_by_name(cmd.name):
            raise DomainError(f"群组名称已存在: {cmd.name}")

        member_ids = list(dict.fromkeys(cmd.member_ids))  # 去重保序
        members: list[Agent] = []
        for agent_id in member_ids:
            agent = await self._agents.get_by_id(agent_id)
            if agent is None:
                raise ValidationError(f"成员 Agent 不存在: {agent_id}")
            members.append(agent)

        coordinator = Agent(
            name=f"协调者-{cmd.name}",
            avatar="🧭",
            role="Coordinator",
            agent_system=AgentSystem.MOCK,
            is_system=True,
        )
        await self._agents.save(coordinator)

        group = Group(
            name=cmd.name,
            description=cmd.description,
            coordinator_id=coordinator.id,
            member_ids=member_ids,
            workspace_path=cmd.workspace_path,
        )
        await self._groups.save(group)

        return self._to_response(group, coordinator, members)

    async def check_name(self, name: str) -> tuple[bool, str | None]:
        if await self._groups.exists_by_name(name):
            return False, "名称已存在"
        return True, None

    async def list(self) -> list[GroupResponse]:
        groups = await self._groups.list()
        responses: list[GroupResponse] = []
        for group in groups:
            coordinator = await self._agents.get_by_id(group.coordinator_id)
            agents = await asyncio.gather(
                *(self._agents.get_by_id(mid) for mid in group.member_ids),
            )
            members = [a for a in agents if a is not None]
            responses.append(self._to_response(group, coordinator, members))
        return responses

    async def rename(self, cmd: RenameGroupCommand) -> GroupResponse:
        group = await self._groups.get_by_id(cmd.group_id)
        if group is None:
            raise NotFoundError(f"群组不存在: {cmd.group_id}")
        if await self._groups.exists_by_name(cmd.name, exclude_id=cmd.group_id):
            raise DomainError(f"群组名称已存在: {cmd.name}")
        updated = await self._groups.update_name(cmd.group_id, cmd.name)
        coordinator = await self._agents.get_by_id(group.coordinator_id)
        return self._to_response(updated or group, coordinator, [])

    async def delete(self, cmd: DeleteGroupCommand) -> None:
        if await self._groups.get_by_id(cmd.group_id) is None:
            raise NotFoundError(f"群组不存在: {cmd.group_id}")
        await self._groups.delete(cmd.group_id)

    @staticmethod
    def _to_response(
        group: Group, coordinator: Agent | None, members: list[Agent]
    ) -> GroupResponse:
        if coordinator is not None:
            coord = GroupCoordinatorResponse(
                id=coordinator.id,
                name=coordinator.name,
                role=coordinator.role,
                agent_system=str(coordinator.agent_system),
                is_system=coordinator.is_system,
            )
        else:  # 数据异常兜底：协调者丢失也不让列表崩
            coord = GroupCoordinatorResponse(
                id=group.coordinator_id,
                name="协调者",
                role="Coordinator",
                agent_system="mock",
                is_system=True,
            )
        return GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            coordinator=coord,
            members=[GroupMemberResponse(id=a.id, name=a.name, role=a.role) for a in members],
            created_at=group.created_at,
        )
