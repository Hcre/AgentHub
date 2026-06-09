"""AgentService 集成测试（L3 + L1 SQLite）。"""

import pytest

from app.application.commands import CreateAgentCommand, UpdateAgentCommand
from app.application.services import AgentService
from app.core.events import InMemoryEventBus
from app.core.exceptions import DomainError
from app.infrastructure.repositories import PostgresAgentRepository


def _make_service(db) -> AgentService:  # type: ignore[no-untyped-def]
    return AgentService(PostgresAgentRepository(db), InMemoryEventBus())


@pytest.mark.asyncio
async def test_create_agent(db_session) -> None:  # type: ignore[no-untyped-def]
    svc = _make_service(db_session)
    resp = await svc.create(
        CreateAgentCommand(
            name="FrontendAgent",
            avatar="http://x/a.png",
            role="前端专家",
        )
    )
    assert resp.name == "FrontendAgent"
    assert resp.status == "offline"
    # 不泄露 api_key
    assert not hasattr(resp, "api_key")


@pytest.mark.asyncio
async def test_duplicate_name_rejected(db_session) -> None:  # type: ignore[no-untyped-def]
    svc = _make_service(db_session)
    cmd = CreateAgentCommand(
        name="Dup",
        avatar="a",
        role="r",
    )
    await svc.create(cmd)
    with pytest.raises(DomainError):
        await svc.create(cmd)


@pytest.mark.asyncio
async def test_update_agent(db_session) -> None:  # type: ignore[no-untyped-def]
    svc = _make_service(db_session)
    created = await svc.create(
        CreateAgentCommand(
            name="A",
            avatar="a",
            role="r",
        )
    )
    updated = await svc.update(UpdateAgentCommand(agent_id=created.id, role="新角色"))
    assert updated.role == "新角色"
