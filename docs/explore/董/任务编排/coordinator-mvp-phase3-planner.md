# Phase 3 详细实现方案 — Planner（真 LLM 分解，MVP 种子式）

> 日期：2026-06-06 | 状态：✅ 已实现 | 属于：[[coordinator-mvp-implementation-plan]] Phase 3
> 依据：[[coordinator-mvp-phase3-planner-spec]]
> 91 passed, ruff clean。旧 coordinator.py / harness.py 已删。

---

## 0. 本相目标

换掉 FakePlanner，接真 LLM。MVP：种子单次文本补全，**只产 mechanical acceptance，不读文件**（tool_use 循环是标准档）。

---

## 1. 异常体系（spec §3/§6.2）

```python
# app/core/exceptions.py 追加

class CoordinatorError(DomainError):
    """协调者子系统异常基类。"""

class PlanParseError(CoordinatorError):
    """LLM 输出 JSON 解析失败（容错+重试耗尽）。"""

class PlanEmptyError(CoordinatorError):
    """LLM 产出空 plan（0 任务），或群组无可用 Agent。"""

class PlannerLLMError(CoordinatorError):
    """LLM API 调用失败（超时/限流/key，退避重试耗尽）。"""
```

---

## 2. ports.py — TextLLM Protocol + PlanContext 扩字段（spec §6.3/§7.1/§7.4）

```python
# ports.py 追加/修改

@dataclass
class PlanContext:
    """Planner 分解的输入种子（MVP：gather_context 预注入，不读文件）。"""
    task: str
    workers: tuple[str, ...]          # 可用 worker 名（build_graph 校验用）
    repo_tree: str = ""               # 目录树快照
    constraints: tuple[str, ...] = () # 交接约束（"错误提示中文"…）
    agents_desc: str = ""             # ★ 成员能力描述
    design_doc: str | None = None     # 用户上传文档


class TextLLM(Protocol):
    """LLM 文本补全可注入接缝。返回**原始文本**——容错解析归 Planner。

    不用 chat_structured（它返回 dict 且畸形 JSON 时吞错），
    否则 Planner 拿不到原始文本做容错+重试。
    真实现包 Anthropic 客户端，返回 content[0].text。
    """
    async def complete(self, prompt: str) -> str: ...
```

> **关键决策**：JSON 容错放 Planner，不放适配器。`TextLLM.complete` 返回原始文本，
> Planner 拿到才能做「多层容错 + 带反馈重试」。这是层次正确的选择。

---

## 3. context.py（spec §1.1/§7.4/§9）

同步 IO 工具，异步调用方用 `asyncio.to_thread(gather_context, ...)` 包装。

```python
"""Coordinator 上下文组装（spec §1.1 gather_context）。

MVP：机械收集仓库元数据 + Agent 注册表 + 约束，全注入 PlanContext。
只读，路径限边界（realpath + startswith workspace），不可越界、不可写。
同步 IO——异步调用方用 `await asyncio.to_thread(gather_context, ...)`。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from app.domain.task_engine.ports import PlanContext

logger = logging.getLogger(__name__)

_TREE_DEPTH = 3
_IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist",
    "__pycache__", ".mypy_cache", ".pytest_cache",
}
_STACK_FILES = ["package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml"]
_MAX_TREE_LINES = 200
_MAX_STACK_BYTES = 5 * 1024
_MAX_DOC_BYTES = 30 * 1024


def _safe_workspace_path(workspace: str, relative: str = ".") -> str:
    """路径限边界：防 ../../etc/passwd 越界，锁死在 workspace 内。"""
    root = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(root, relative))
    if not (full == root or full.startswith(root + os.sep)):
        raise ValueError(f"越界访问被拒: {relative}")
    return full


def _list_tree(workspace: str, max_depth: int = _TREE_DEPTH) -> str:
    root = _safe_workspace_path(workspace)
    if (Path(root) / ".git").exists():
        try:
            result = subprocess.run(
                ["git", "ls-files"], cwd=root,
                capture_output=True, text=True, timeout=10, check=False,
            )
            files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        except (OSError, subprocess.SubprocessError):
            files = []
    else:
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            rel_depth = len(Path(dirpath).relative_to(root).parts)
            if rel_depth >= max_depth:
                dirnames.clear()
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
            for f in filenames:
                files.append(str(Path(dirpath).relative_to(root) / f))

    trimmed: set[str] = set()
    for f in sorted(files):
        parts = Path(f).parts
        trimmed.add(str(Path(*parts[:max_depth])) + ("/..." if len(parts) > max_depth else ""))
    return "\n".join(sorted(trimmed)[:_MAX_TREE_LINES])


def _read_stack_info(workspace: str) -> str:
    root = _safe_workspace_path(workspace)
    parts = []
    for name in _STACK_FILES:
        path = Path(root) / name
        if path.is_file():
            try:
                content = path.read_text("utf-8", errors="replace")[:_MAX_STACK_BYTES]
                parts.append(f"--- {name} ---\n{content}")
            except OSError:
                continue
    return "\n".join(parts)


def _discover_commands(workspace: str) -> str:
    root = _safe_workspace_path(workspace)
    cmds = []
    pkg_json = Path(root) / "package.json"
    if pkg_json.exists():
        try:
            scripts = json.loads(pkg_json.read_text("utf-8")).get("scripts", {})
            for key in ("test", "build", "lint", "typecheck"):
                if key in scripts:
                    cmds.append(f"npm run {key}")
            if not cmds:
                cmds.append("npx tsc --noEmit")
        except (OSError, json.JSONDecodeError):
            pass
    if (Path(root) / "pyproject.toml").exists() or (Path(root) / "setup.py").exists():
        cmds.append("pytest")
    if (Path(root) / "Makefile").exists():
        cmds.append("make test")
    return ", ".join(cmds)


def _build_agents_desc(workers: list[str]) -> str:
    return "\n".join(f"- {w}" for w in workers)


def gather_context(
    task_text: str,
    workers: list[str],
    workspace: str | None = None,
    constraints: tuple[str, ...] | None = None,
    design_doc: str | None = None,
) -> PlanContext:
    """组装 PlanContext 种子。只读，零副作用。

    Args:
        task_text: 用户需求文本
        workers: 群成员 Agent 名（空 → plan() 时 PlanEmptyError）
        workspace: 代码仓库路径（None = 纯文本任务）
        constraints: 硬约束清单
        design_doc: 用户上传设计文档路径
    """
    repo_tree = ""
    if workspace and os.path.isdir(workspace):
        _safe_workspace_path(workspace)
        repo_tree = _list_tree(workspace)
        _read_stack_info(workspace)   # 当前未进 PlanContext，预留标准档注入
        _discover_commands(workspace)

    doc_text: str | None = None
    if design_doc:
        doc_path = Path(design_doc)
        if doc_path.is_file():
            doc_text = doc_path.read_text("utf-8", errors="replace")[:_MAX_DOC_BYTES]

    return PlanContext(
        task=task_text,
        workers=tuple(workers),
        repo_tree=repo_tree,
        constraints=constraints or (),
        agents_desc=_build_agents_desc(workers),
        design_doc=doc_text,
    )
```

---

## 4. planner.py（spec §1-§8）

```python
"""Planner — LLM 任务分解（spec §1.1）。

MVP：种子 + 单次文本补全，上下文预注入，零工具。只产 mechanical acceptance。
纯推理——不改状态、不派发、不验证。无状态——每次调用现组装上下文。

容错归 Planner：TextLLM.complete 返回**原始文本**，Planner 自己 extract_json + 解析重试。
（不用 chat_structured——它返回 dict 且畸形 JSON 时吞错，拿不到原始文本。）
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from typing import Any

from app.core.exceptions import PlanEmptyError, PlannerLLMError, PlanParseError
from app.domain.task_engine.dag import Check, TaskDef, TaskGraph, build_graph
from app.domain.task_engine.ports import PlanContext, TextLLM

logger = logging.getLogger(__name__)

MAX_PARSE_RETRIES = 3   # JSON 解析失败重试（带反馈再 prompt）
MAX_API_RETRIES = 2     # LLM API 瞬时错误退避重试
API_RETRY_DELAY = 1.0   # 秒（指数退避基数）

_VALID_ACCEPTANCE_KINDS = {"mechanical"}
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)


# ── JSON 容错解析（spec §3.1）──────────────────────────────────────────────


def _try_parse(s: str) -> dict[str, Any] | None:
    """先 json.loads，再 ast.literal_eval（原生处理 Python True/False/None/单引号，
    不做字符串替换——避免把 "True Love" 腐蚀成 "true Love"）。"""
    try:
        r = json.loads(s)
        return r if isinstance(r, dict) else None
    except json.JSONDecodeError:
        pass
    try:
        r = ast.literal_eval(s)
        return r if isinstance(r, dict) else None
    except (ValueError, SyntaxError):
        return None


def _first_balanced_block(text: str) -> str | None:
    """提取首个平衡的 {} 块。"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _fence(text: str) -> str | None:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else None


def extract_json(text: str) -> dict[str, Any]:
    """三层回退：① 整段 ② code fence ③ 首个平衡 {} 块（每层 json+ast）。"""
    for candidate in (text, _fence(text), _first_balanced_block(text)):
        if candidate is None:
            continue
        obj = _try_parse(candidate)
        if obj is not None:
            return obj
    raise PlanParseError(f"JSON 解析失败（整段/fence/平衡块均不可解），前 200 字符: {text[:200]}")


# ── TaskDef 解析（spec §7.2→§7.3）─────────────────────────────────────────


def parse_task_defs(raw: dict[str, Any]) -> list[TaskDef]:
    """从 LLM 结构化输出解析 TaskDef。守卫：非 mechanical 拒绝 / 去重 / 必填字段。

    worker 合法性、环、悬空依赖由 build_graph 校验（不在此重复）。
    """
    task_dicts = raw.get("tasks")
    if not isinstance(task_dicts, list) or not task_dicts:
        raise PlanEmptyError("LLM 产出空 plan（tasks 为空或非数组）")

    defs: list[TaskDef] = []
    seen_ids: set[str] = set()

    for t in task_dicts:
        tid = str(t.get("id", "")).strip()
        title = str(t.get("title", "")).strip()
        worker = str(t.get("suggested_worker", "")).strip()
        if not tid or not title or not worker:
            raise PlanParseError(
                f"Task 缺必填字段: id={tid!r} title={title!r} worker={worker!r}"
            )
        if tid in seen_ids:
            raise PlanParseError(f"重复 task id: {tid!r}")
        seen_ids.add(tid)

        acceptance: list[Check] = []
        for c in t.get("acceptance", []):
            kind = str(c.get("kind", ""))
            if kind not in _VALID_ACCEPTANCE_KINDS:
                raise PlanParseError(
                    f"Task {tid} 含非 mechanical acceptance: kind={kind!r}。"
                    f"MVP 只支持 mechanical；无法机械验证请标 no_verify=true"
                )
            acceptance.append(Check(
                kind=kind,
                spec=str(c.get("spec", "")),
                expect=str(c["expect"]) if c.get("expect") is not None else None,
            ))

        deps_raw = t.get("depends_on", []) or []
        deps = list(dict.fromkeys(str(d) for d in deps_raw))  # 去重保序

        defs.append(TaskDef(
            id=tid,
            title=title,
            description=str(t.get("description", "")).strip(),
            suggested_worker=worker,
            depends_on=deps,
            acceptance=acceptance,
            no_verify=bool(t.get("no_verify", False)),
        ))

    return defs


# ── prompt（spec §7.2）─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是 AgentHub 的任务协调者。将用户需求分解为可执行的子任务 DAG。

## 规则
1. 每个子任务必须有明确输出 + 验收标准（acceptance）。
2. acceptance 必须用 mechanical 命令（pytest/tsc/npm build 等），能抓退出码。
   无法机械验证的 → 标 no_verify=true 并在 description 说明原因。
3. suggested_worker 必须从下方「可用 Agent」中选择，不得捏造。
4. depends_on 为其他 task 的 id 数组；无依赖 = 空数组；不得成环。
5. 粒度：一个 Task = 一个 Agent 一次对话能独立完成的工作量。文件范围写进 description。

## 输出格式
只输出合法 JSON，不要任何额外文字：
{
  "tasks": [
    {"id": "短横线命名", "title": "简短标题", "description": "详细描述+文件范围",
     "suggested_worker": "Agent 名称", "depends_on": [],
     "acceptance": [{"kind": "mechanical", "spec": "命令", "expect": null}],
     "no_verify": false}
  ],
  "rationale": "为什么这样分解"
}"""


def build_user_prompt(ctx: PlanContext) -> str:
    parts = [f"## 用户需求\n{ctx.task}"]
    if ctx.constraints:
        parts.append("## 硬约束\n" + "\n".join(f"- {c}" for c in ctx.constraints))
    parts.append(f"## 可用 Agent\n{ctx.agents_desc}")
    if ctx.repo_tree:
        parts.append(f"## 仓库目录结构\n```\n{ctx.repo_tree}\n```")
    if ctx.design_doc:
        parts.append(f"## 设计文档\n{ctx.design_doc}")
    return "\n\n".join(parts)


# ── Planner ────────────────────────────────────────────────────────────────


class SeedPlanner:
    """MVP Planner：种子上下文 + 单次文本补全 → TaskDef[]。无状态、纯推理。"""

    def __init__(self, llm: TextLLM) -> None:
        self._llm = llm

    async def plan(self, ctx: PlanContext) -> list[TaskDef]:
        if not ctx.workers:
            raise PlanEmptyError("群组无可用 Agent，无法分解任务")

        base_prompt = SYSTEM_PROMPT + "\n\n" + build_user_prompt(ctx)
        raw = await self._plan_with_parse_retry(base_prompt)
        defs = parse_task_defs(raw)
        build_graph(defs, set(ctx.workers))  # 环/悬空/未知 worker/空 acceptance 校验
        logger.info("Planner 产出 %d 个 Task（rationale=%s）",
                    len(defs), str(raw.get("rationale", ""))[:100])
        return defs

    async def final_answer(self, graph: TaskGraph) -> str:
        lines = [
            f"- {n.task.title}: {n.status}"
            + (f" — {n.output[:200]}" if n.output else "")
            for n in graph.nodes.values()
        ]
        prompt = (
            "你是 AgentHub 的任务协调者。以下是任务执行结果。"
            "请用简洁中文向用户汇报完成情况（创建了什么、验收结果）。\n\n"
            + "\n".join(lines)
        )
        return await self._complete_with_backoff(prompt)  # 文本，不解析 JSON

    # ── 内部：解析重试（带反馈再 prompt）─────────────────────────────────

    async def _plan_with_parse_retry(self, base_prompt: str) -> dict[str, Any]:
        feedback = ""
        for attempt in range(MAX_PARSE_RETRIES + 1):
            text = await self._complete_with_backoff(base_prompt + feedback)
            try:
                return extract_json(text)
            except PlanParseError as exc:
                if attempt >= MAX_PARSE_RETRIES:
                    raise PlanParseError(
                        f"JSON 解析重试 {MAX_PARSE_RETRIES} 次仍失败；"
                        f"最后输出前 200 字符: {text[:200]}"
                    ) from exc
                logger.warning("JSON 解析失败（第 %d 次），带反馈重试", attempt + 1)
                feedback = (
                    f"\n\n[系统] 上次输出不是合法 JSON（{exc}）。"
                    f"请严格只输出符合格式的 JSON，不要任何额外文字。"
                )
        raise PlanParseError("unreachable")

    # ── 内部：LLM 调用 + 瞬时错误退避 ───────────────────────────────────

    async def _complete_with_backoff(self, prompt: str) -> str:
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                return await self._llm.complete(prompt)
            except (TimeoutError, ConnectionError) as exc:  # 瞬时 → 退避重试
                if attempt >= MAX_API_RETRIES:
                    raise PlannerLLMError(
                        f"LLM API 退避重试 {MAX_API_RETRIES} 次仍失败"
                    ) from exc
                logger.warning("LLM 瞬时错误（第 %d 次），退避重试: %s", attempt + 1, exc)
                await asyncio.sleep(API_RETRY_DELAY * (2 ** attempt))
            except Exception as exc:  # 非瞬时（auth 等）不重试
                raise PlannerLLMError(f"LLM 调用失败: {exc}") from exc
        raise PlannerLLMError("unreachable")
```

### 4.1 与原始计划的 9 处修正

| # | 严重度 | 原计划 | 实际实现 | 原因 |
|---|:---:|--------|---------|------|
| 1 | 🔴 | `StructuredLLM` Protocol，`chat_structured()→dict` | `TextLLM` Protocol，`complete()→str` | chat_structured 畸形 JSON 时吞错；Planner 需要原始文本做容错+带反馈重试 |
| 2 | 🔴 | test 用 `ValueError` 断言 build_graph 失败 | test 用 `DagValidationError` | build_graph 实际抛 `DagValidationError`，不是裸 `ValueError` |
| 3 | 🟠 | 全局字符串替换 `True→true` | `ast.literal_eval` 原生处理 Python 字面量 | 避免把字符串内容（"True Love"）腐蚀成 "true Love"。加了回归测试 |
| 4 | 🟠 | prompt 含不存在的 `submit_task_plan` tool | prompt 纯 JSON，不提 tool | `PLAN_TOOL_SCHEMA` 死代码——MVP 没用 Anthropic tool_use |
| 5 | 🟠 | API 所有异常统一退避重试 | 瞬时（Timeout/Connection）退避重试；auth 等不重试 | auth 错误退避不会恢复，只会浪费重试配额。加了 `test_plan_auth_error_no_retry` |
| 6 | 🟡 | `final_answer` 取 `resp["summary"]` 键 | 直接用 `complete()` 返回的文本 | 输出就是文本总结，不需要再包 dict |
| 7 | 🟡 | `CoordinatoredError` 命名 | `CoordinatorError` | 拼写修正 |
| 8 | 🟡 | `parse_task_defs(raw, workers)` 传入 workers 参数 | `parse_task_defs(raw)` | worker 校验归 `build_graph`，不在 `parse_task_defs` 里重复 |
| 9 | 🟡 | context.py 异步 IO | context.py 同步 IO + `asyncio.to_thread` 包装 | `subprocess`/`open` 是同步的；异步调用方自己包装 |

---

## 5. tests/test_context.py

```python
"""gather_context 测试（spec §1.4/§10）。git 测试不要求 commit。"""

from __future__ import annotations

import os

import pytest

from app.domain.task_engine.context import (
    _list_tree,
    _safe_workspace_path,
    gather_context,
)


class TestSafeWorkspacePath:
    def test_within_workspace(self, tmp_path):
        p = _safe_workspace_path(str(tmp_path), "src")
        assert p.startswith(str(tmp_path))

    def test_traversal_blocked(self, tmp_path):
        with pytest.raises(ValueError, match="越界"):
            _safe_workspace_path(str(tmp_path), "../../etc/passwd")


class TestListTree:
    def test_empty_dir(self, tmp_path):
        assert _list_tree(str(tmp_path)) == ""

    def test_git_repo_no_commit(self, tmp_path):
        """git init + 文件暂存即被 ls-files 发现，不需要 commit。"""
        os.system(f"cd {tmp_path} && git init -q && touch a.py b.py && git add .")
        tree = _list_tree(str(tmp_path))
        assert "a.py" in tree

    def test_non_git_walk(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x")
        tree = _list_tree(str(tmp_path))
        assert "src/main.py" in tree

    def test_ignore_dirs_dedup(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x")
        tree = _list_tree(str(tmp_path))
        assert "src" in tree
        assert "node_modules" not in tree


class TestGatherContext:
    def test_basic(self):
        ctx = gather_context("创建登录页", ["前端Agent", "后端Agent"])
        assert ctx.task == "创建登录页"
        assert ctx.workers == ("前端Agent", "后端Agent")
        assert "前端Agent" in ctx.agents_desc

    def test_empty_workers(self):
        ctx = gather_context("task", [])
        assert ctx.workers == ()

    def test_with_constraints(self):
        ctx = gather_context("task", ["w"], constraints=("中文提示",))
        assert "中文提示" in ctx.constraints

    def test_with_design_doc(self, tmp_path):
        doc = tmp_path / "design.md"
        doc.write_text("# 设计文档")
        ctx = gather_context("task", ["w"], design_doc=str(doc))
        assert ctx.design_doc is not None
        assert "设计文档" in ctx.design_doc
```

---

## 6. tests/test_planner.py

```python
"""Planner 测试（spec §1.4/§10）。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PlanEmptyError, PlannerLLMError, PlanParseError
from app.domain.task_engine.dag import DagValidationError
from app.domain.task_engine.planner import (
    SeedPlanner,
    build_user_prompt,
    extract_json,
    parse_task_defs,
)
from app.domain.task_engine.ports import PlanContext


# ── extract_json（spec §3.1 三层回退）───────────────────────────────────────

class TestExtractJson:
    def test_pure_json(self):
        assert extract_json('{"tasks":[]}') == {"tasks": []}

    def test_code_fence(self):
        assert extract_json('```json\n{"tasks":[]}\n```') == {"tasks": []}

    def test_ast_literal_python_dict(self):
        """ast.literal_eval 原生处理 Python 单引号/True/False/None。"""
        raw = "{'tasks': [{'id': 't1'}], 'ok': True, 'none_val': None}"
        result = extract_json(raw)
        assert result["tasks"][0]["id"] == "t1"
        assert result["ok"] is True
        assert result["none_val"] is None

    def test_balanced_brace(self):
        raw = '前缀 {"tasks": [{"id": "t1"}]} 后缀'
        assert extract_json(raw)["tasks"][0]["id"] == "t1"

    def test_true_love_not_corrupted(self):
        """ast.literal_eval 不做字符串替换 —— "True Love" 不会变成 "true Love"。"""
        raw = '{"title": "True Love", "flag": True}'
        result = extract_json(raw)
        assert result["title"] == "True Love"   # 不被腐蚀
        assert result["flag"] is True           # 字面量正确

    def test_all_layers_fail(self):
        with pytest.raises(PlanParseError):
            extract_json("这不是 JSON 也不是 Python 字面量")


# ── parse_task_defs（spec §7.2→§7.3）────────────────────────────────────────

class TestParseTaskDefs:
    def test_valid(self):
        raw = {"tasks": [{
            "id": "t1", "title": "创建页面", "description": "写代码",
            "suggested_worker": "前端Agent", "depends_on": [],
            "acceptance": [{"kind": "mechanical", "spec": "npm run build"}],
        }]}
        defs = parse_task_defs(raw)
        assert len(defs) == 1

    def test_empty_raises_PlanEmptyError(self):
        with pytest.raises(PlanEmptyError):
            parse_task_defs({"tasks": []})

    def test_not_array_raises_PlanEmptyError(self):
        with pytest.raises(PlanEmptyError):
            parse_task_defs({"tasks": "not_array"})

    def test_missing_required_field_raises(self):
        raw = {"tasks": [{"id": "", "title": "", "suggested_worker": ""}]}
        with pytest.raises(PlanParseError):
            parse_task_defs(raw)

    def test_non_mechanical_acceptance_rejected(self):
        raw = {"tasks": [{
            "id": "t1", "title": "x", "description": "x",
            "suggested_worker": "w", "depends_on": [],
            "acceptance": [{"kind": "llm_judge", "spec": "评审"}],
        }]}
        with pytest.raises(PlanParseError, match="非 mechanical"):
            parse_task_defs(raw)

    def test_depends_on_dedup(self):
        raw = {"tasks": [{
            "id": "t1", "title": "x", "description": "x",
            "suggested_worker": "w", "depends_on": ["t0", "t0", "t0"],
            "acceptance": [], "no_verify": True,
        }]}
        defs = parse_task_defs(raw)
        assert defs[0].depends_on == ["t0"]

    def test_duplicate_id_rejected(self):
        raw = {"tasks": [
            {"id": "t1", "title": "a", "description": "a",
             "suggested_worker": "w", "depends_on": [], "acceptance": []},
            {"id": "t1", "title": "b", "description": "b",
             "suggested_worker": "w", "depends_on": [], "acceptance": []},
        ]}
        with pytest.raises(PlanParseError, match="重复"):
            parse_task_defs(raw)


# ── SeedPlanner 集成（mock TextLLM）─────────────────────────────────────────

@pytest.fixture
def plan_ctx():
    return PlanContext(
        task="创建登录页面",
        workers=("前端Agent", "后端Agent", "测试Agent"),
        agents_desc="- 前端Agent\n- 后端Agent\n- 测试Agent",
        repo_tree="frontend/src/\nbackend/app/",
        constraints=("中文错误提示",),
    )


def _plan_dict():
    return {
        "tasks": [
            {"id": "t-fe", "title": "LoginForm", "description": "组件",
             "suggested_worker": "前端Agent", "depends_on": [],
             "acceptance": [{"kind": "mechanical", "spec": "npm run build"}]},
            {"id": "t-be", "title": "auth API", "description": "端点",
             "suggested_worker": "后端Agent", "depends_on": [],
             "acceptance": [{"kind": "mechanical", "spec": "pytest"}]},
            {"id": "t-e2e", "title": "E2E 测试", "description": "测试",
             "suggested_worker": "测试Agent",
             "depends_on": ["t-fe", "t-be"],
             "acceptance": [{"kind": "mechanical", "spec": "pytest tests/e2e/"}]},
        ],
    }


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete = AsyncMock()
    return llm


@pytest.mark.asyncio
async def test_plan_happy_path(mock_llm, plan_ctx):
    mock_llm.complete.return_value = json.dumps(_plan_dict())
    planner = SeedPlanner(mock_llm)
    defs = await planner.plan(plan_ctx)
    assert len(defs) == 3

@pytest.mark.asyncio
async def test_plan_empty_workers_raises(mock_llm):
    ctx = PlanContext(task="x", workers=(), agents_desc="")
    planner = SeedPlanner(mock_llm)
    with pytest.raises(PlanEmptyError):
        await planner.plan(ctx)

@pytest.mark.asyncio
async def test_plan_json_parse_retry_then_success(mock_llm, plan_ctx):
    """第 1 次返回非法文本 → 带反馈重试 → 第 2 次成功。"""
    mock_llm.complete.side_effect = ["not json", json.dumps(_plan_dict())]
    planner = SeedPlanner(mock_llm)
    defs = await planner.plan(plan_ctx)
    assert len(defs) == 3
    assert mock_llm.complete.call_count == 2

@pytest.mark.asyncio
async def test_plan_parse_retry_exhausted(mock_llm, plan_ctx):
    """连续非法文本 → MAX_PARSE_RETRIES 耗尽 → PlanParseError。"""
    mock_llm.complete.return_value = "not json"
    planner = SeedPlanner(mock_llm)
    with pytest.raises(PlanParseError):
        await planner.plan(plan_ctx)
    # MAX_PARSE_RETRIES=3 → 1 原始 + 3 重试 = 4 次
    assert mock_llm.complete.call_count == 4

@pytest.mark.asyncio
async def test_plan_transient_error_retry(mock_llm, plan_ctx):
    """Timeout → 退避重试 → 成功。"""
    mock_llm.complete.side_effect = [TimeoutError("timeout"), json.dumps(_plan_dict())]
    planner = SeedPlanner(mock_llm)
    defs = await planner.plan(plan_ctx)
    assert len(defs) == 3
    assert mock_llm.complete.call_count == 2

@pytest.mark.asyncio
async def test_plan_auth_error_no_retry(mock_llm, plan_ctx):
    """非瞬时错误（auth）不重试，直接 PlannerLLMError。"""
    mock_llm.complete.side_effect = RuntimeError("invalid API key")
    planner = SeedPlanner(mock_llm)
    with pytest.raises(PlannerLLMError):
        await planner.plan(plan_ctx)
    assert mock_llm.complete.call_count == 1  # 不重试

@pytest.mark.asyncio
async def test_plan_validation_rejects_bad_dag(mock_llm, plan_ctx):
    """悬空依赖 → build_graph → DagValidationError。"""
    bad = {"tasks": [{
        "id": "t1", "title": "x", "description": "x",
        "suggested_worker": "前端Agent", "depends_on": ["t-ghost"], "acceptance": [],
    }]}
    mock_llm.complete.return_value = json.dumps(bad)
    planner = SeedPlanner(mock_llm)
    with pytest.raises(DagValidationError):
        await planner.plan(plan_ctx)

@pytest.mark.asyncio
async def test_final_answer(mock_llm):
    mock_llm.complete.return_value = "全部完成：LoginForm + auth API + E2E 测试已通过"
    from app.domain.task_engine.dag import TaskGraph
    graph = TaskGraph(nodes={})
    planner = SeedPlanner(mock_llm)
    result = await planner.final_answer(graph)
    assert "全部完成" in result
```

---

## 7. 清理旧债

| 文件 | 动作 |
|------|------|
| `coordinator.py`（48 行） | **删** |
| `harness.py`（68 行） | **删** |

---

## 8. 与 Orchestrator 的接法

```python
from app.domain.task_engine.planner import SeedPlanner
from app.domain.task_engine.context import gather_context
import asyncio

# TextLLM 适配器：包 Anthropic 客户端 → complete() 返回 content[0].text
class AnthropicTextLLM:
    def __init__(self, client): self._client = client
    async def complete(self, prompt: str) -> str:
        resp = await self._client.messages.create(
            model=..., max_tokens=2048, messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

llm = AnthropicTextLLM(session.get_anthropic_client())
planner = SeedPlanner(llm)

# gather_context 是同步 IO → to_thread 包装
ctx = await asyncio.to_thread(
    gather_context,
    task_text=task,
    workers=registry.list_names(),
    workspace=session.workspace_path,
    constraints=handoff.constraints,
    design_doc=handoff.design_doc,
)
defs = await planner.plan(ctx)
```

---

## 9. 验收

```bash
# context.py 独立测试（8 用例）
pytest tests/test_context.py -q

# planner.py 测试（20 用例）
pytest tests/test_planner.py -q

# 全套回归（task_engine 91 passed）
pytest tests/test_dag.py tests/test_scheduler.py tests/test_fsm.py \
       tests/test_orchestrator.py tests/test_verifier.py \
       tests/test_context.py tests/test_planner.py -q

# ruff
ruff check app/domain/task_engine/ app/core/exceptions.py tests/
```

---

## 关联文档

- [[coordinator-mvp-phase3-planner-spec]] 本相规格
- [[coordinator-mvp-implementation-plan]] Phase 3 概述
- [[coordinator-subsystem-collaborators]] §5.2 Planner / §6 上下文
