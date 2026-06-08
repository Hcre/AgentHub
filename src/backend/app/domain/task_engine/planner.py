"""Planner — LLM 任务分解（spec §1.1）。

MVP：种子 + 单次文本补全，上下文预注入，零工具。只产 mechanical acceptance（spec §1.2/§4）。
纯推理——不改状态、不派发、不验证。无状态——每次调用 Orchestrator 现场组装上下文。

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
from app.domain.task_engine.dag import Check, TaskDef, build_graph
from app.domain.task_engine.ports import PlanContext, TextLLM

logger = logging.getLogger(__name__)

MAX_PARSE_RETRIES = 3  # JSON 解析失败重试（带反馈再 prompt）
MAX_API_RETRIES = 2  # LLM API 瞬时错误退避重试
API_RETRY_DELAY = 1.0  # 秒（指数退避基数）

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


def extract_json(text: str) -> dict[str, Any]:
    """三层回退：① 整段 ② code fence ③ 首个平衡 {} 块（每层 json+ast）。"""
    for candidate in (text, _fence(text), _first_balanced_block(text)):
        if candidate is None:
            continue
        obj = _try_parse(candidate)
        if obj is not None:
            return obj
    raise PlanParseError(f"JSON 解析失败（整段/fence/平衡块均不可解），前 200 字符: {text[:200]}")


def _fence(text: str) -> str | None:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else None


# ── TaskDef 解析（spec §7.2→§7.3）─────────────────────────────────────────


def parse_task_defs(raw: dict[str, Any]) -> list[TaskDef]:
    """从 LLM 结构化输出解析 TaskDef（守卫：非 mechanical 拒绝/去重/必填字段）。

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

    # 注：MVP 无 final_answer——末尾汇总由 Orchestrator 机械生成（成败只锚机器判定，
    # 零 LLM，见 orchestrator._build_summary）。标准档再加 is_request_satisfied。

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
