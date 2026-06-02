"""Coordinator：LLM 驱动的任务分解（架构文档 §6.2，S13）。

MVP 阶段为骨架，M3 接入真实 LLM 结构化输出 + Few-shot Prompt。
"""

from __future__ import annotations

from app.domain.llm.protocol import UnifiedAgent
from app.domain.task_engine.harness import Harness, PlannedTask, TaskPlan


class Coordinator:
    """协调者：构造 prompt → LLM 结构化分解 → Harness 校验。"""

    def __init__(self, llm: UnifiedAgent, harness: Harness) -> None:
        self._llm = llm
        self._harness = harness

    async def decompose(
        self,
        message: str,
        available_agents: list[str],
        conversation_history: list[dict] | None = None,
    ) -> TaskPlan:
        prompt = self._build_prompt(message, available_agents, conversation_history or [])
        decision = await self._llm.chat_structured(prompt)
        plan = self._parse(decision)
        return self._harness.validate(plan)

    def _build_prompt(self, message: str, agents: list[str], history: list[dict]) -> str:
        # M3：替换为精心设计的 System Prompt + Few-shot 示例
        return (
            "你是任务协调者。将用户需求分解为可分派给以下 Agent 的子任务，"
            f"输出 JSON。\n可用 Agent: {agents}\n用户需求: {message}"
        )

    def _parse(self, decision: dict) -> TaskPlan:
        raw_tasks = decision.get("tasks", [])
        tasks = [
            PlannedTask(
                title=t.get("title", ""),
                description=t.get("description", ""),
                suggested_worker=t.get("suggested_worker", ""),
                depends_on=t.get("depends_on", []),
            )
            for t in raw_tasks
        ]
        return TaskPlan(tasks=tasks, rationale=decision.get("rationale", ""))
