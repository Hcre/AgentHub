"""Memory CRUD 路由（/api/agents/{agent_id}/memories）。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_memory_service
from app.application.commands import CreateMemoryCommand, UpdateMemoryCommand
from app.application.services.memory_service import MemoryService
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryStatsOut, MemoryUpdate

router = APIRouter(prefix="/api/agents/{agent_id}/memories", tags=["memories"])

MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    agent_id: UUID,
    svc: MemoryServiceDep,
    memory_type: str | None = None,
) -> list[MemoryOut]:
    items = await svc.list_by_agent(agent_id, memory_type)
    return [MemoryOut.model_validate(m.__dict__) for m in items]


@router.get("/stats", response_model=MemoryStatsOut)
async def memory_stats(agent_id: UUID, svc: MemoryServiceDep) -> MemoryStatsOut:
    data = await svc.stats(agent_id)
    return MemoryStatsOut(**data)


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(agent_id: UUID, memory_id: UUID, svc: MemoryServiceDep) -> MemoryOut:
    m = await svc.get(memory_id)
    return MemoryOut.model_validate(m.__dict__)


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    agent_id: UUID, body: MemoryCreate, svc: MemoryServiceDep
) -> MemoryOut:
    cmd = CreateMemoryCommand(
        name=body.name,
        description=body.description,
        memory_type=body.memory_type,
        content=body.content,
        source="manual",
        group_id=body.group_id,
        metadata=body.metadata,
    )
    # user_id 暂与 agent_id 相同（未接入 JWT 时），接入后替换
    m = await svc.create(agent_id=agent_id, user_id=agent_id, cmd=cmd)
    return MemoryOut.model_validate(m.__dict__)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    agent_id: UUID, memory_id: UUID, body: MemoryUpdate, svc: MemoryServiceDep
) -> MemoryOut:
    patch = UpdateMemoryCommand(
        content=body.content,
        memory_type=body.memory_type,
        pinned=body.pinned,
        metadata=body.metadata,
    )
    m = await svc.update(memory_id, patch=patch)
    return MemoryOut.model_validate(m.__dict__)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_memory(agent_id: UUID, memory_id: UUID, svc: MemoryServiceDep) -> None:
    await svc.delete(memory_id)
