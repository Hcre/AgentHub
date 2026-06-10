"""Agent 路由（PRD §6.1，架构 §4.1）。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_agent_draft_service, get_agent_service
from app.application.commands import (
    CreateAgentCommand,
    DeleteAgentCommand,
    UpdateAgentCommand,
)
from app.application.services import AgentService
from app.application.services.agent_draft_service import AgentDraftService
from app.core.exceptions import PlanParseError
from app.schemas.agent import (
    AgentCreateRequest,
    AgentDraftOut,
    AgentDraftRequest,
    AgentOut,
    AgentUpdateRequest,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])

ServiceDep = Annotated[AgentService, Depends(get_agent_service)]
DraftServiceDep = Annotated[AgentDraftService, Depends(get_agent_draft_service)]


@router.post("/draft-from-chat", response_model=AgentDraftOut)
async def draft_agent_from_chat(body: AgentDraftRequest, svc: DraftServiceDep) -> AgentDraftOut:
    """对话式创建：自然语言描述 → LLM 抽取结构化草稿（前端预览后再调 POST /api/agents 落库）。"""
    try:
        draft = await svc.draft(body.description)
    except PlanParseError as exc:
        raise HTTPException(status_code=422, detail=f"草稿解析失败: {exc}") from exc
    return AgentDraftOut(**draft)


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


@router.get("/coordinator/credential")
async def get_coordinator_credential(
    svc: ServiceDep,
) -> dict:
    """读取已保存的协调者凭证（用于前端回填表单）。优先内存，fallback DB。"""
    from app.application.services.reactive_router import _coordinator_credential
    from app.core.security import decrypt_secret

    # 1) 内存中有 → 直接返回（不泄露完整 key，只给前缀提示）
    if _coordinator_credential:
        key = _coordinator_credential.get("api_key", "")
        return {
            "provider": _coordinator_credential.get("provider", ""),
            "model": _coordinator_credential.get("model", ""),
            "base_url": _coordinator_credential.get("base_url", ""),
            "api_key_prefix": key[:6] + "…" if len(key) > 6 else "",
            "has_key": bool(key),
        }

    # 2) 查 DB：从任一 system agent 的 settings 读取
    agents = await svc._repo.list()
    for a in agents:
        if a.is_system:
            creds = a.settings.get("coordinator_credential", {}) if isinstance(a.settings, dict) else {}
            if creds and creds.get("api_key_encrypted"):
                decrypted = decrypt_secret(creds["api_key_encrypted"])
                # 回填内存（下次 Planner/ReactiveRouter 直接用）
                _coordinator_credential["provider"] = creds.get("provider", "")
                _coordinator_credential["api_key"] = decrypted
                _coordinator_credential["model"] = creds.get("model", "")
                _coordinator_credential["base_url"] = creds.get("base_url", "")
                return {
                    "provider": creds.get("provider", ""),
                    "model": creds.get("model", ""),
                    "base_url": creds.get("base_url", ""),
                    "api_key_prefix": decrypted[:6] + "…" if len(decrypted) > 6 else "",
                    "has_key": True,
                }
            break

    return {"provider": "", "model": "", "base_url": "", "api_key_prefix": "", "has_key": False}


@router.put("/coordinator/credential")
async def set_coordinator_credential(
    body: dict,
    svc: ServiceDep,
) -> dict:
    """前端点星设置协调者凭证 → 同步写入到所有系统 Agent。"""
    provider = body.get("provider", "")
    api_key = body.get("api_key", "")
    model = body.get("model", "")
    base_url = body.get("base_url", "")
    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="provider and api_key are required")
    count = await svc.update_coordinator_credential(
        provider=str(provider), api_key=str(api_key), model=str(model), base_url=str(base_url) if base_url else ""
    )
    # 同步更新内存中的全局凭证（ReactiveRouter + Planner 实时读取）
    from app.application.services.reactive_router import _coordinator_credential

    _coordinator_credential["provider"] = str(provider)
    _coordinator_credential["api_key"] = str(api_key)
    _coordinator_credential["model"] = str(model)
    _coordinator_credential["base_url"] = str(base_url) if base_url else ""
    return {"updated": count}


@router.get("/coordinator/credential/status")
async def credential_status() -> dict:
    """快速检查：协调者凭证是否已配置（不发起网络请求）。"""
    from app.application.services.reactive_router import _coordinator_credential

    if _coordinator_credential.get("api_key"):
        return {
            "configured": True,
            "provider": _coordinator_credential.get("provider", ""),
            "model": _coordinator_credential.get("model", ""),
        }
    return {"configured": False}


@router.post("/coordinator/credential/test")
async def test_coordinator_credential(
    body: dict,
) -> dict:
    """用当前表单参数测试 API 连通性（不保存）。发一条简短消息，检查是否返回有效响应。"""
    import time as _time

    provider = body.get("provider", "")
    api_key = body.get("api_key", "")
    model = body.get("model", "")
    base_url = body.get("base_url", "")

    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="provider and api_key are required")
    if provider == "anthropic":
        raise HTTPException(status_code=400, detail="anthropic provider 暂不支持连通测试，请用 OpenAI 兼容 provider")

    if not model:
        raise HTTPException(status_code=400, detail="model is required for OpenAI-compatible providers")

    from openai import AsyncOpenAI

    url = base_url or ("https://api.deepseek.com/v1" if provider == "deepseek" else None)
    client = AsyncOpenAI(api_key=api_key, base_url=url) if url else AsyncOpenAI(api_key=api_key)

    t0 = _time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
            timeout=15,
        )
        latency = int((_time.monotonic() - t0) * 1000)
        reply = resp.choices[0].message.content or "" if resp.choices else ""
        return {
            "ok": True,
            "latency_ms": latency,
            "model": model,
            "reply_preview": reply[:100],
        }
    except Exception as e:
        latency = int((_time.monotonic() - t0) * 1000)
        return {"ok": False, "error": str(e)[:500], "latency_ms": latency}
