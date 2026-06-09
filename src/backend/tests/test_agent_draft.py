"""M1#4 对话式创建队友 · 启发式抽取测试（api/routers/agents._heuristic_extract）。

owner override 降级实现：LLM 未接入时用关键词 + 模板抽取。本套验证抽取协议
（role / skills / name / source），LLM 接入后替换 _heuristic_extract 仍应满足同形态。

三路径（T-03）：
1. 正常：含明确角色 + 技术关键词 → role 命中、skills 含关键词、source 固定
2. 边界：无任何关键词 → role 降级「通用助手」、skills 兜底为 [role]
3. 边界：超长描述 → name 截断到 30 字符内
"""

from __future__ import annotations

import base64
import os

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")

from app.api.routers.agents import AgentDraft, _heuristic_extract


def test_extract_frontend_review_hits_role_and_skills() -> None:
    """路径 1：前端 + React + 性能 关键词 → role/skills 正确，source 固定。"""
    draft = _heuristic_extract(
        "我想要一个帮我做前端 React 代码审查的助手，重点看性能和可维护性"
    )
    assert isinstance(draft, AgentDraft)
    # 「前端」先于「审查」命中（dict 顺序），role 为前端开发
    assert draft.role == "前端开发"
    assert "React" in draft.skills
    assert "性能" in draft.skills
    assert draft.source == "draft-from-chat"
    assert draft.name  # 非空
    assert draft.system_prompt  # 模板已填


def test_extract_backend_role() -> None:
    """后端关键词 → role=后端开发，技术栈进 skills。"""
    draft = _heuristic_extract("帮我创建一个 FastAPI 后端 API 开发助手")
    assert draft.role == "后端开发"
    assert "FastAPI" in draft.skills
    assert "API" in draft.skills


def test_extract_no_keyword_degrades_to_generic() -> None:
    """路径 2（边界）：无角色/技术关键词 → role 降级通用助手，skills 兜底为 [role]。"""
    draft = _heuristic_extract("随便帮我弄点东西")
    assert draft.role == "通用助手"
    assert draft.skills == ["通用助手"]
    assert draft.source == "draft-from-chat"


def test_extract_long_description_truncates_name() -> None:
    """路径 3（边界）：超长描述 → name 截断在 30 字符内。"""
    draft = _heuristic_extract("帮我建一个" + "超" * 100 + "的助手")
    assert len(draft.name) <= 30
