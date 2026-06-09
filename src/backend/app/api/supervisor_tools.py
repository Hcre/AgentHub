"""AgentHub Supervisor MCP 工具端点（SSE transport）。

Supervisor CLI 通过 --mcp-config 连接，调用工具查看/操作任务状态。

工具列表：
  supervisor_get_plan        — 查看当前任务计划和各步骤状态
  supervisor_nudge           — 轻推某个 worker（注入 pending note）
  supervisor_replan          — 触发重新分解任务
  supervisor_trigger_deploy  — 触发部署
  supervisor_send_message    — 发送消息到群聊

session_id 传递方式：与 step-tools/memory 一致，通过 SSE URL ?session_id=<uuid> 注入。
工具 handler 从 _ACTIVE registry 读取 CoordinatorRun 状态。

注：本文件 **不** 写 `from __future__ import annotations`——mcp 1.12.x 的 Tool.from_function
用 `inspect.signature(fn)` 拿到的注解必须是真实类。
"""

import logging
from contextvars import ContextVar
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP as _FastMCP
    _MCP_AVAILABLE = True
except ImportError:
    _FastMCP = None  # type: ignore[assignment,misc]
    _MCP_AVAILABLE = False
    logger.info("mcp 包未安装，MCP supervisor 工具不可用（pip install mcp）")

from app.application.services.coordinator_run import _ACTIVE, post_system_background

# ContextVar：工具函数读 session_id，由 ASGI wrapper 在请求维度注入
_session_id_ctx: ContextVar[str] = ContextVar("agenthub_supervisor_session_id", default="")


class _SupervisorMCPWrapper:
    """ASGI wrapper：从 SSE URL 提取 session_id。

    与 _AgentMCPWrapper / _StepToolsMCPWrapper 同模式：
      客户端 GET /sse?session_id=<uuid> → wrapper 在请求维度 set ContextVar
      → 工具 handler 从 ContextVar 读取 session_id。
    """

    def __init__(self, mcp_asgi: Any) -> None:
        self._app = mcp_asgi

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        qs: str = scope.get("query_string", b"").decode()
        params: dict[str, str] = dict(
            p.split("=", 1) for p in qs.split("&") if "=" in p
        )

        if path.endswith("/sse"):
            t_sess = _session_id_ctx.set(params.get("session_id", ""))
            logger.info(
                "MCP supervisor-tools SSE 连接 session=%s agent=%s group=%s",
                params.get("session_id", ""),
                params.get("agent_id", ""),
                params.get("group_id", ""),
            )
            try:
                await self._app(scope, receive, send)
            finally:
                _session_id_ctx.reset(t_sess)
        else:
            await self._app(scope, receive, send)


def _resolve_session_id() -> UUID | None:
    """从 ContextVar 读取 session_id 并解析为 UUID。失败 → None。"""
    raw = _session_id_ctx.get()
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        logger.warning("supervisor-tools: 无效 session_id=%s", raw)
        return None


def _get_run() -> Any | None:
    """获取当前 session 的 CoordinatorRun（从进程级 registry）。"""
    sid = _resolve_session_id()
    if sid is None:
        return None
    return _ACTIVE.get(sid)


# ── MCP app 构建 ─────────────────────────────────────────────────────────────


def _build_mcp_app() -> Any | None:
    if not _MCP_AVAILABLE:
        return None

    mcp = _FastMCP("agenthub-supervisor-tools")

    @mcp.tool()
    async def supervisor_get_plan() -> dict[str, Any]:
        """查看当前任务计划和各步骤状态。

        返回完整的 DAG 计划：每个步骤的 id、worker、状态、依赖，以及整体统计。
        Supervisor 用此工具了解当前进展，决定是否需要干预。
        """
        sid = _resolve_session_id()
        if sid is None:
            return {"error": "session_id 未解析或无效"}
        run = _ACTIVE.get(sid)
        if run is None:
            return {"error": "当前 session 无活跃任务", "session_id": str(sid)}

        orch = run.orchestrator
        if orch is None or orch.graph is None:
            return {"error": "Orchestrator 未就绪", "session_id": str(sid)}

        nodes = orch.graph.nodes
        steps = []
        for tid, node in nodes.items():
            steps.append({
                "id": tid,
                "title": node.task.title,
                "suggested_worker": node.task.suggested_worker,
                "worker": node.worker or node.task.suggested_worker,
                "status": node.status.value,
                "depends_on": list(node.task.depends_on),
                "retries": node.retries,
                "fail_reason": node.fail_reason or "",
                "output": (node.output or "")[:500],  # 截断长输出
            })

        total = len(steps)
        status_counts: dict[str, int] = {}
        for s in steps:
            st = s["status"]
            status_counts[st] = status_counts.get(st, 0) + 1

        return {
            "session_id": str(sid),
            "run_id": run.run_id,
            "total_steps": total,
            "status_counts": status_counts,
            "steps": steps,
        }

    @mcp.tool()
    async def supervisor_nudge(worker: str, message: str) -> dict[str, Any]:
        """轻推某个 worker。

        将消息投递到指定 worker 的消息桶，worker 在下一个 turn 或 resume 时会收到。
        适用场景：worker 卡住/未交卷/需要提醒。

        Args:
            worker: 目标 worker 名称（与计划中的 suggested_worker 对应）
            message: 推送给 worker 的消息内容
        """
        run = _get_run()
        if run is None:
            return {"error": "当前 session 无活跃任务"}

        if not worker:
            return {"error": "worker 不能为空"}

        try:
            run.enqueue_note(message, worker)
            logger.info("supervisor nudge: worker=%s session=%s", worker, _resolve_session_id())
            return {"status": "ok", "worker": worker, "message": message}
        except Exception as exc:
            logger.exception("supervisor nudge 失败")
            return {"error": str(exc)}

    @mcp.tool()
    async def supervisor_replan(requirement: str) -> dict[str, Any]:
        """触发重新分解任务。

        调用 CoordinatorRun 的 replan 流程：重 LLM 分解 → 计算 diff → 换图。
        破坏性 replan（有在跑 worker）会先 abort 在飞 worker 再换图。

        Args:
            requirement: 新的需求描述，供 Planner 重新分解
        """
        run = _get_run()
        if run is None:
            return {"error": "当前 session 无活跃任务"}

        if not requirement.strip():
            return {"error": "requirement 不能为空"}

        sid = _resolve_session_id()
        try:
            planned = await run.plan_replan(requirement)
            if planned is None:
                return {"error": "Orchestrator 未就绪，无法 replan"}

            new_tasks, diff = planned
            await run.replan(new_tasks, force=True)
            logger.info(
                "supervisor replan: session=%s old_count=%s new_count=%s",
                sid, len(diff.completed) + len(diff.running), diff.new_count,
            )
            return {
                "status": "ok",
                "message": f"已重新分解：新计划 {diff.new_count} 项",
                "was_running": diff.running,
                "was_completed": diff.completed,
                "new_count": diff.new_count,
            }
        except Exception as exc:
            logger.exception("supervisor replan 失败")
            return {"error": str(exc)}

    @mcp.tool()
    async def supervisor_trigger_deploy() -> dict[str, Any]:
        """触发部署。

        在全部任务完成后，调用此工具触发部署流程。
        当前版本产出一个部署请求消息到群聊，提醒用户确认部署。
        """
        run = _get_run()
        sid = _resolve_session_id()
        if run is None:
            return {"error": "当前 session 无活跃任务"}

        orch = run.orchestrator
        if orch is None:
            return {"error": "Orchestrator 未就绪"}

        # 检查是否全部完成
        if orch.graph is not None:
            all_done = all(
                n.status.value == "completed" for n in orch.graph.nodes.values()
            )
            if not all_done:
                return {
                    "status": "blocked",
                    "message": "并非全部任务完成，暂不部署。请确认所有步骤已通过后再试。",
                }

        # 发系统消息通知部署
        deploy_msg = (
            "🚀 部署请求：所有任务已完成。\n"
            "Supervisor 建议将当前 workspace 变更部署到线上。请确认后执行部署。"
        )
        try:
            coordinator_id = run.orchestrator._ctx.workers[0] if run.orchestrator and run.orchestrator.graph else None
            await post_system_background(sid, deploy_msg, coordinator_id)  # type: ignore[arg-type]
            logger.info("supervisor trigger_deploy: session=%s", sid)
            return {"status": "ok", "message": "部署请求已发送到群聊，请确认后执行。"}
        except Exception as exc:
            logger.exception("supervisor trigger_deploy 失败")
            return {"error": str(exc)}

    @mcp.tool()
    async def supervisor_send_message(message: str) -> dict[str, Any]:
        """发送消息到群聊。

        Supervisor 用此工具向群聊发送消息，所有群成员可见。
        适用于：需要通知用户、报告进展、询问决策等场景。

        Args:
            message: 要发送的消息内容
        """
        sid = _resolve_session_id()
        if sid is None:
            return {"error": "session_id 未解析或无效"}

        if not message.strip():
            return {"error": "message 不能为空"}

        try:
            await post_system_background(sid, message, None)
            logger.info("supervisor send_message: session=%s len=%d", sid, len(message))
            return {"status": "ok", "message": "消息已发送"}
        except Exception as exc:
            logger.exception("supervisor send_message 失败")
            return {"error": str(exc)}

    return _SupervisorMCPWrapper(mcp.sse_app())


_mcp_asgi = _build_mcp_app()


def get_supervisor_mcp_asgi() -> Any | None:
    """返回包了 _SupervisorMCPWrapper 的 ASGI app，供 main.py mount 使用。"""
    return _mcp_asgi
