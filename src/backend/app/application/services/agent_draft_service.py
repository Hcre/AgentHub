"""AgentDraftService（L3）：自然语言描述 → 结构化 Agent 草稿（对话式创建）。

用户用一句话描述想要的队友 → LLM 抽取 name/role/avatar/system_prompt/capability_tags
→ 前端预览草稿 → 确认后走既有 POST /api/agents 落库。

容错沿用 planner.extract_json（整段/fence/平衡块三层回退）。
"""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.domain.task_engine.planner import extract_json
from app.domain.task_engine.ports import TextLLM

_PROMPT = """\
你是 AgentHub 的「队友设计师」。用户会用自然语言描述他们想要的一个 AI 队友（Agent）。
请把描述抽取成结构化草稿，只输出一个 JSON 对象（不要任何额外文字），字段：
- name: 简短中文名（≤12 字）
- role: 一句话角色定位（≤30 字）
- avatar: 一个 emoji
- system_prompt: 给这个 Agent 的系统提示（中文，2-5 句，明确它的职责/风格/边界）
- capability_tags: 3-6 个能力标签（中文短词数组）

用户描述：
{description}

只输出 JSON：
"""


class AgentDraftService:
    def __init__(self, llm: TextLLM) -> None:
        self._llm = llm

    async def draft(self, description: str) -> dict:
        description = (description or "").strip()
        if not description:
            raise ValidationError("E_AGENT_DRAFT_EMPTY: 描述不能为空")
        text = await self._llm.complete(_PROMPT.format(description=description))
        raw = extract_json(text)  # 解析失败抛 PlanParseError，路由转 422

        tags = raw.get("capability_tags") or raw.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return {
            "name": (str(raw.get("name", "")).strip() or "新队友")[:24],
            "role": str(raw.get("role", "")).strip()[:64],
            "avatar": (str(raw.get("avatar", "")).strip() or "🤖")[:8],
            "system_prompt": str(raw.get("system_prompt", "")).strip(),
            "capability_tags": [str(t).strip() for t in tags if str(t).strip()][:8],
        }
