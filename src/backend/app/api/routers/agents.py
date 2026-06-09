"""Agent 路由（PRD §6.1，架构 §4.1 + M1#4 对话式创建）。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

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


# ── M1#4 对话式创建（owner override）：用户描述 → LLM 抽取 → Agent 草稿 JSON ──

class DraftFromChatRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)


class AgentDraft(BaseModel):
    name: str
    role: str = ""
    system_prompt: str = ""
    skills: list[str] = []
    # owner override 标志：标识草稿来源（前端展示用）
    source: str = "draft-from-chat"


@router.post("/draft-from-chat", response_model=AgentDraft)
async def draft_agent_from_chat(body: DraftFromChatRequest) -> AgentDraft:
    """M1#4 对话式创建：用户自然语言描述 → Agent 草稿 JSON。

    owner override 实现：当前 LLM 凭证依赖运行时未稳定接入，先用启发式抽取
    （关键词匹配 + 模板填充），保留 LLM 抽取接口形态。LLM 接入替换 _heuristic_extract
    一处即可。

    不持久化 — 仅返回草稿，前端展示后调 POST /api/agents 真正创建。
    """
    return _heuristic_extract(body.description)


def _heuristic_extract(description: str) -> AgentDraft:
    """启发式抽取（owner override 降级：LLM 未接入时使用）。

    后续可替换为调 LLM。
    """
    desc = description.strip()
    role = ""
    role_keywords = {
        "前端": "前端开发",
        "后端": "后端开发",
        "审查": "代码审查",
        "review": "代码审查",
        "测试": "测试",
        "运维": "运维",
        "数据": "数据分析",
        "产品": "产品",
        "设计": "设计",
    }
    for kw, r in role_keywords.items():
        if kw.lower() in desc.lower():
            role = r
            break
    if not role:
        role = "通用助手"

    name = ""
    for marker in ["帮我建一个", "帮我创建", "建一个", "创建"]:
        idx = desc.find(marker)
        if idx >= 0:
            tail = desc[idx + len(marker):].split("Agent")[0].split("agent")[0].strip()
            if tail:
                name = tail[:30]
                break
    if not name:
        name = desc[:30].strip() or "新 Agent"

    skills: list[str] = []
    for kw in ["React", "Vue", "TypeScript", "Python", "FastAPI", "PostgreSQL", "Redis",
               "Docker", "性能", "安全", "测试", "重构", "架构", "API"]:
        if kw.lower() in desc.lower() and kw not in skills:
            skills.append(kw)
    if not skills:
        skills = [role]

    system_prompt = (
        f"你是{name}，专注于{role}。\n"
        f"用户需求：{desc}\n"
        "请基于上述需求提供专业、准确、可执行的回复。"
    )

    return AgentDraft(
        name=name,
        role=role,
        system_prompt=system_prompt,
        skills=skills,
        source="draft-from-chat",
    )


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreateRequest, svc: ServiceDep) -> AgentOut:
    resp = await svc.create(
        CreateAgentCommand(
            name=body.name,
            avatar=body.avatar,
            role=body.role,
            agent_system=str(body.agent_system),
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


# -- 协调者凭证：前端点星后写入所有 is_system=true 的 Agent --


@router.put("/coordinator/credential")
async def set_coordinator_credential(
    body: dict,
    svc: ServiceDep,
) -> dict:
    """前端点星设置协调者凭证 → 同步写入到所有系统 Agent。"""
    provider = body.get("provider", "")
    api_key = body.get("api_key", "")
    model = body.get("model", "")
    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="provider and api_key are required")
    count = await svc.update_coordinator_credential(
        provider=str(provider), api_key=str(api_key), model=str(model)
    )
    # 同步更新内存中的全局凭证（ReactiveRouter 实时读取）
    from app.application.services.reactive_router import _coordinator_credential

    _coordinator_credential["provider"] = str(provider)
    _coordinator_credential["api_key"] = str(api_key)
    _coordinator_credential["model"] = str(model)
    return {"updated": count}
