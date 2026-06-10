"""AgentDraftService（对话式创建）测试：自然语言 → 结构化草稿。"""

from __future__ import annotations

import pytest

from app.application.services.agent_draft_service import AgentDraftService
from app.core.exceptions import PlanParseError, ValidationError


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.seen: str | None = None

    async def complete(self, prompt: str) -> str:
        self.seen = prompt
        return self.reply


@pytest.mark.asyncio
async def test_draft_extracts_fields_from_json() -> None:
    llm = _FakeLLM(
        '```json\n{"name":"前端专家","role":"React 重构","avatar":"🎨",'
        '"system_prompt":"你专注前端。","capability_tags":["React","TS","重构"]}\n```'
    )
    svc = AgentDraftService(llm)
    draft = await svc.draft("我想要一个会 React 重构的前端队友")
    assert draft["name"] == "前端专家"
    assert draft["role"] == "React 重构"
    assert draft["avatar"] == "🎨"
    assert "前端" in draft["system_prompt"]
    assert draft["capability_tags"] == ["React", "TS", "重构"]
    assert "我想要一个会 React 重构" in (llm.seen or "")


@pytest.mark.asyncio
async def test_draft_fills_defaults_for_missing_fields() -> None:
    svc = AgentDraftService(_FakeLLM('{"role":"打杂"}'))
    draft = await svc.draft("随便来个助手")
    assert draft["name"] == "新队友"  # 缺 name → 默认
    assert draft["avatar"] == "🤖"  # 缺 avatar → 默认
    assert draft["capability_tags"] == []


@pytest.mark.asyncio
async def test_draft_empty_description_rejected() -> None:
    svc = AgentDraftService(_FakeLLM("{}"))
    with pytest.raises(ValidationError, match="E_AGENT_DRAFT_EMPTY"):
        await svc.draft("   ")


@pytest.mark.asyncio
async def test_draft_unparseable_llm_output_raises() -> None:
    svc = AgentDraftService(_FakeLLM("抱歉我不会输出 JSON"))
    with pytest.raises(PlanParseError):
        await svc.draft("造个队友")


@pytest.mark.asyncio
async def test_draft_caps_tags_to_8() -> None:
    tags = ",".join(f'"t{i}"' for i in range(12))
    svc = AgentDraftService(_FakeLLM(f'{{"name":"x","capability_tags":[{tags}]}}'))
    draft = await svc.draft("很多标签")
    assert len(draft["capability_tags"]) == 8
