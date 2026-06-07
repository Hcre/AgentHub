"""Agent 路由（PRD §6.1，架构 §4.1）。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_agent_service
from app.application.commands import (
    CreateAgentCommand,
    DeleteAgentCommand,
    UpdateAgentCommand,
)
from app.application.services import AgentService
from app.schemas.agent import AgentCreateRequest, AgentOut, AgentUpdateRequest

router = APIRouter(prefix="/api/agents", tags=["agents"])

ServiceDep = Annotated[AgentService, Depends(get_agent_service)]


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreateRequest, svc: ServiceDep) -> AgentOut:
    resp = await svc.create(
        CreateAgentCommand(
            name=body.name,
            avatar=body.avatar,
            role=body.role,
            agent_system=str(body.agent_system),
            provider=str(body.provider),
            model=body.model,
            api_key=body.api_key,
            base_url=body.base_url,
            skills=body.skills,
            system_prompt=body.system_prompt,
            settings=body.settings,
            template_name=body.template_name,
            template_id=body.created_from_template_id,
        )
    )
    return AgentOut(**resp.__dict__)


@router.get("", response_model=list[AgentOut])
async def list_agents(
    svc: ServiceDep,
    status_filter: str | None = None,
    capability: str | None = None,
) -> list[AgentOut]:
    items = await svc.list(status=status_filter, capability=capability)
    return [AgentOut(**i.__dict__) for i in items]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: UUID, svc: ServiceDep) -> AgentOut:
    return AgentOut(**(await svc.get(agent_id)).__dict__)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: UUID, body: AgentUpdateRequest, svc: ServiceDep) -> AgentOut:
    resp = await svc.update(
        UpdateAgentCommand(
            agent_id=agent_id,
            name=body.name,
            avatar=body.avatar,
            role=body.role,
            agent_system=str(body.agent_system) if body.agent_system else None,
            provider=str(body.provider) if body.provider else None,
            model=body.model,
            api_key=body.api_key,
            base_url=body.base_url,
            skills=body.skills,
            capability_tags=body.capability_tags,
            settings=body.settings,
            system_prompt=body.system_prompt,
        )
    )
    return AgentOut(**resp.__dict__)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, svc: ServiceDep) -> Response:
    await svc.delete(DeleteAgentCommand(agent_id=agent_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
