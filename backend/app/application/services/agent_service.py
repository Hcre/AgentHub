"""AgentService（L3）：Agent 增删改查用例（架构文档 §6.1）。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.application.commands import (
    CreateAgentCommand,
    DeleteAgentCommand,
    UpdateAgentCommand,
)
from app.application.dto import AgentResponse
from app.core.events import EventBus
from app.core.exceptions import DomainError, NotFoundError
from app.core.security import encrypt_secret
from app.domain.entities.agent import Agent
from app.domain.enums import Provider
from app.domain.events import AgentCreated, AgentDeleted, AgentUpdated
from app.domain.repositories import AgentRepository


class AgentService:
    def __init__(self, agent_repo: AgentRepository, event_bus: EventBus) -> None:
        self._repo = agent_repo
        self._bus = event_bus

    async def create(self, cmd: CreateAgentCommand) -> AgentResponse:
        if await self._repo.exists_by_name(cmd.name):
            raise DomainError(f"Agent name 已存在: {cmd.name}")

        agent = Agent(
            name=cmd.name,
            avatar=cmd.avatar,
            role=cmd.role,
            provider=Provider(cmd.provider),
            model=cmd.model,
            api_key_encrypted=encrypt_secret(cmd.api_key),  # L3 负责加密
            skills=cmd.skills,
            system_prompt=cmd.system_prompt,
        )
        await self._repo.save(agent)
        await self._bus.publish(
            AgentCreated(
                agent_id=agent.id,
                name=agent.name,
                provider=str(agent.provider),
                model=agent.model,
            )
        )
        return AgentResponse.from_domain(agent)

    async def update(self, cmd: UpdateAgentCommand) -> AgentResponse:
        agent = await self._repo.get_by_id(cmd.agent_id)
        if agent is None:
            raise NotFoundError(f"Agent 不存在: {cmd.agent_id}")

        changes: dict[str, object] = {
            "name": cmd.name,
            "avatar": cmd.avatar,
            "role": cmd.role,
            "model": cmd.model,
            "skills": cmd.skills,
            "capability_tags": cmd.capability_tags,
            "settings": cmd.settings,
            "system_prompt": cmd.system_prompt,
        }
        if cmd.provider is not None:
            changes["provider"] = Provider(cmd.provider)
        if cmd.api_key is not None:
            changes["api_key_encrypted"] = encrypt_secret(cmd.api_key)

        changed_fields = agent.update(**changes)
        if changed_fields:
            await self._repo.save(agent)
            await self._bus.publish(
                AgentUpdated(agent_id=agent.id, changed_fields=changed_fields)
            )
        return AgentResponse.from_domain(agent)

    async def delete(self, cmd: DeleteAgentCommand) -> None:
        agent = await self._repo.get_by_id(cmd.agent_id)
        if agent is None:
            raise NotFoundError(f"Agent 不存在: {cmd.agent_id}")
        await self._repo.soft_delete(cmd.agent_id)
        await self._bus.publish(AgentDeleted(agent_id=cmd.agent_id))

    async def get(self, agent_id: UUID) -> AgentResponse:
        agent = await self._repo.get_by_id(agent_id)
        if agent is None:
            raise NotFoundError(f"Agent 不存在: {agent_id}")
        return AgentResponse.from_domain(agent)

    async def list(
        self, *, status: str | None = None, capability: str | None = None
    ) -> list[AgentResponse]:
        agents = await self._repo.list(status=status, capability=capability)
        return [AgentResponse.from_domain(a) for a in agents]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
