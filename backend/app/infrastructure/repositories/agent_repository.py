"""PostgresAgentRepository：AgentRepository 的 SQLAlchemy 实现。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.agent import Agent
from app.domain.enums import AgentStatus, Provider
from app.domain.repositories import AgentRepository
from app.infrastructure.db.models import AgentModel


def _to_domain(m: AgentModel) -> Agent:
    return Agent(
        id=m.id,
        name=m.name,
        avatar=m.avatar,
        role=m.role,
        provider=Provider(m.provider),
        model=m.model,
        api_key_encrypted=m.api_key_encrypted,
        status=AgentStatus(m.status),
        workload=m.workload,
        is_system=m.is_system,
        skills=list(m.skills or []),
        capability_tags=list(m.capability_tags or []),
        system_prompt=m.system_prompt,
        settings=dict(m.settings or {}),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class PostgresAgentRepository(AgentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, agent: Agent) -> None:
        existing = await self._s.get(AgentModel, agent.id)
        if existing is None:
            self._s.add(_to_model(agent))
        else:
            _update_model(existing, agent)
        await self._s.flush()

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        m = await self._s.get(AgentModel, agent_id)
        if m is None or m.is_deleted:
            return None
        return _to_domain(m)

    async def exists_by_name(self, name: str) -> bool:
        stmt = select(AgentModel.id).where(
            AgentModel.name == name, AgentModel.is_deleted.is_(False)
        )
        return (await self._s.execute(stmt)).first() is not None

    async def list(
        self, *, status: str | None = None, capability: str | None = None
    ) -> list[Agent]:
        stmt = select(AgentModel).where(AgentModel.is_deleted.is_(False))
        if status:
            stmt = stmt.where(AgentModel.status == status)
        rows = (await self._s.execute(stmt)).scalars().all()
        agents = [_to_domain(m) for m in rows]
        if capability:
            agents = [a for a in agents if capability in a.capability_tags]
        return agents

    async def soft_delete(self, agent_id: UUID) -> None:
        m = await self._s.get(AgentModel, agent_id)
        if m is not None:
            m.is_deleted = True
            await self._s.flush()


def _to_model(a: Agent) -> AgentModel:
    return AgentModel(
        id=a.id,
        name=a.name,
        avatar=a.avatar,
        role=a.role,
        provider=str(a.provider),
        model=a.model,
        api_key_encrypted=a.api_key_encrypted,
        status=str(a.status),
        workload=a.workload,
        is_system=a.is_system,
        skills=a.skills,
        capability_tags=a.capability_tags,
        system_prompt=a.system_prompt,
        settings=a.settings,
    )


def _update_model(m: AgentModel, a: Agent) -> None:
    m.name = a.name
    m.avatar = a.avatar
    m.role = a.role
    m.provider = str(a.provider)
    m.model = a.model
    m.api_key_encrypted = a.api_key_encrypted
    m.status = str(a.status)
    m.workload = a.workload
    m.skills = a.skills
    m.capability_tags = a.capability_tags
    m.system_prompt = a.system_prompt
    m.settings = a.settings
