"""Planner 测试（spec §1.4/§10）。TextLLM 返回文本，Planner 自己容错解析。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PlanEmptyError, PlannerLLMError, PlanParseError
from app.domain.task_engine.dag import DagValidationError
from app.domain.task_engine.planner import (
    SeedPlanner,
    extract_json,
    parse_task_defs,
)
from app.domain.task_engine.ports import PlanContext

# ── extract_json（三层回退）────────────────────────────────────────────────


class TestExtractJson:
    def test_pure_json(self):
        assert extract_json('{"tasks":[]}') == {"tasks": []}

    def test_code_fence(self):
        assert extract_json('```json\n{"tasks":[]}\n```') == {"tasks": []}

    def test_python_keywords_via_ast(self):
        r = extract_json('{"tasks": [], "ok": True, "none_val": None}')
        assert r["ok"] is True and r["none_val"] is None

    def test_balanced_brace(self):
        assert extract_json('前缀 {"tasks": [{"id": "t1"}]} 后缀')["tasks"][0]["id"] == "t1"

    def test_single_quotes_via_ast(self):
        assert extract_json("{'tasks': [{'id': 't1'}]}")["tasks"][0]["id"] == "t1"

    def test_string_not_corrupted(self):
        # "True Love" 不应被腐蚀成 "true Love"（旧 bug）
        r = extract_json('{"tasks": [], "title": "True Love"}')
        assert r["title"] == "True Love"

    def test_all_layers_fail(self):
        with pytest.raises(PlanParseError):
            extract_json("这不是 JSON 也不是 Python 字面量")


# ── parse_task_defs ─────────────────────────────────────────────────────────


class TestParseTaskDefs:
    def test_valid(self):
        raw = {"tasks": [{
            "id": "t1", "title": "创建页面", "description": "写代码",
            "suggested_worker": "前端Agent", "depends_on": [],
            "acceptance": [{"kind": "mechanical", "spec": "npm run build"}],
        }]}
        defs = parse_task_defs(raw)
        assert len(defs) == 1 and defs[0].id == "t1"

    def test_empty_raises(self):
        with pytest.raises(PlanEmptyError):
            parse_task_defs({"tasks": []})

    def test_not_array_raises(self):
        with pytest.raises(PlanEmptyError):
            parse_task_defs({"tasks": "not_array"})

    def test_missing_field_raises(self):
        with pytest.raises(PlanParseError):
            parse_task_defs({"tasks": [{"id": "", "title": "", "suggested_worker": ""}]})

    def test_non_mechanical_rejected(self):
        raw = {"tasks": [{
            "id": "t1", "title": "x", "description": "x", "suggested_worker": "w",
            "depends_on": [], "acceptance": [{"kind": "llm_judge", "spec": "评审"}],
        }]}
        with pytest.raises(PlanParseError, match="非 mechanical"):
            parse_task_defs(raw)

    def test_depends_on_dedup(self):
        raw = {"tasks": [{
            "id": "t1", "title": "x", "description": "x", "suggested_worker": "w",
            "depends_on": ["t0", "t0", "t0"], "acceptance": [], "no_verify": True,
        }]}
        assert parse_task_defs(raw)[0].depends_on == ["t0"]

    def test_duplicate_id_rejected(self):
        raw = {"tasks": [
            {"id": "t1", "title": "a", "description": "a", "suggested_worker": "w",
             "depends_on": [], "acceptance": [], "no_verify": True},
            {"id": "t1", "title": "b", "description": "b", "suggested_worker": "w",
             "depends_on": [], "acceptance": [], "no_verify": True},
        ]}
        with pytest.raises(PlanParseError, match="重复"):
            parse_task_defs(raw)


# ── SeedPlanner 集成 ────────────────────────────────────────────────────────


_3TASK_PLAN = {
    "tasks": [
        {"id": "t-fe", "title": "LoginForm", "description": "组件",
         "suggested_worker": "前端Agent", "depends_on": [],
         "acceptance": [{"kind": "mechanical", "spec": "npm run build"}]},
        {"id": "t-be", "title": "auth API", "description": "端点",
         "suggested_worker": "后端Agent", "depends_on": [],
         "acceptance": [{"kind": "mechanical", "spec": "pytest"}]},
        {"id": "t-e2e", "title": "E2E", "description": "测试",
         "suggested_worker": "测试Agent", "depends_on": ["t-fe", "t-be"],
         "acceptance": [{"kind": "mechanical", "spec": "pytest tests/e2e/"}]},
    ],
}


@pytest.fixture
def ctx():
    return PlanContext(
        task="创建登录页面",
        workers=("前端Agent", "后端Agent", "测试Agent"),
        agents_desc="- 前端Agent\n- 后端Agent\n- 测试Agent",
    )


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete = AsyncMock()
    return llm


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    import app.domain.task_engine.planner as mod
    monkeypatch.setattr(mod, "API_RETRY_DELAY", 0)


@pytest.mark.asyncio
async def test_plan_happy(mock_llm, ctx):
    mock_llm.complete.return_value = json.dumps(_3TASK_PLAN)
    defs = await SeedPlanner(mock_llm).plan(ctx)
    assert len(defs) == 3
    assert defs[2].depends_on == ["t-fe", "t-be"]


@pytest.mark.asyncio
async def test_plan_empty_workers(mock_llm):
    with pytest.raises(PlanEmptyError):
        await SeedPlanner(mock_llm).plan(PlanContext(task="x", workers=()))


@pytest.mark.asyncio
async def test_plan_parse_retry_then_success(mock_llm, ctx):
    mock_llm.complete.side_effect = ["这不是JSON", json.dumps(_3TASK_PLAN)]
    defs = await SeedPlanner(mock_llm).plan(ctx)
    assert len(defs) == 3
    assert mock_llm.complete.call_count == 2


@pytest.mark.asyncio
async def test_plan_parse_retry_exhausted(mock_llm, ctx):
    mock_llm.complete.return_value = "永远不是JSON"
    with pytest.raises(PlanParseError):
        await SeedPlanner(mock_llm).plan(ctx)
    assert mock_llm.complete.call_count == 4  # 1 + MAX_PARSE_RETRIES(3)


@pytest.mark.asyncio
async def test_plan_api_retry_then_success(mock_llm, ctx):
    mock_llm.complete.side_effect = [TimeoutError("timeout"), json.dumps(_3TASK_PLAN)]
    defs = await SeedPlanner(mock_llm).plan(ctx)
    assert len(defs) == 3


@pytest.mark.asyncio
async def test_plan_api_retry_exhausted(mock_llm, ctx):
    mock_llm.complete.side_effect = TimeoutError("timeout")
    with pytest.raises(PlannerLLMError):
        await SeedPlanner(mock_llm).plan(ctx)


@pytest.mark.asyncio
async def test_plan_auth_error_no_retry(mock_llm, ctx):
    mock_llm.complete.side_effect = ValueError("invalid api key")
    with pytest.raises(PlannerLLMError):
        await SeedPlanner(mock_llm).plan(ctx)
    assert mock_llm.complete.call_count == 1  # 非瞬时不重试


@pytest.mark.asyncio
async def test_plan_validation_rejects_dangling_dep(mock_llm, ctx):
    mock_llm.complete.return_value = json.dumps({
        "tasks": [{"id": "t1", "title": "x", "description": "x",
                   "suggested_worker": "前端Agent", "depends_on": ["t-ghost"],
                   "acceptance": [], "no_verify": True}],
    })
    with pytest.raises(DagValidationError):
        await SeedPlanner(mock_llm).plan(ctx)


@pytest.mark.asyncio
async def test_plan_validation_rejects_unknown_worker(mock_llm, ctx):
    mock_llm.complete.return_value = json.dumps({
        "tasks": [{"id": "t1", "title": "x", "description": "x",
                   "suggested_worker": "不存在Agent", "depends_on": [],
                   "acceptance": [{"kind": "mechanical", "spec": "true"}]}],
    })
    with pytest.raises(DagValidationError):
        await SeedPlanner(mock_llm).plan(ctx)


# 注：final_answer 已移出 Planner（B 方案）——汇总改由 Orchestrator 机械生成；
# 测试见 tests/test_orchestrator.py 的 test_summary_*。
