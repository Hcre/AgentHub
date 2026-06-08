"""AgentHub MCP Step-Tools 端点（SSE transport）。

Worker CLI 通过 --mcp-config 连接，调用 task_complete 工具宣告 step 完成。

设计决策（coordinator-v4-R1 §6.4）：
- task_complete(summary)：worker 宣告子目标达成 → Harness step → VERIFYING → COMPLETED
- 这是**唯一**结构化信号。worker 提问/说话走正常文本流推群聊，不需要专用 tool。
  流结束没调 task_complete = not_done（没交卷，不是失败），等用户回话 --resume 续跑。
- 终结工具检测是结构判断（tool_use name 匹配），不是文本模式匹配——零猜测。
- v4 已删 ask tool（v3 §11.2 残留）：worker 能正常说话，不需要用 tool 来提问。

agent_id/session_id/group_id 传递方式：
  客户端在 SSE URL 加 ?agent_id=<uuid>&session_id=<uuid>&group_id=<uuid>，
  ASGI wrapper 拦截后将 session_id→{agent_id,session_id,group_id} 写入映射，
  POST /messages/ 时按 session_id 查映射并注入三个 ContextVar。
  tool handler 从 ContextVar 读取，不需要 worker 传参。
"""

import logging
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP as _FastMCP

    _MCP_AVAILABLE = True
except ImportError:
    _FastMCP = None  # type: ignore[assignment,misc]
    _MCP_AVAILABLE = False
    logger.info("mcp 包未安装，MCP step-tools 端点不可用（pip install mcp）")

# ── ContextVar：tool handler 从请求维度读取（由 ASGI wrapper 在 POST 时注入）──

_agent_id_ctx: ContextVar[str] = ContextVar("agenthub_step_agent_id", default="")
_session_id_ctx: ContextVar[str] = ContextVar("agenthub_step_session_id", default="")
_group_id_ctx: ContextVar[str] = ContextVar("agenthub_step_group_id", default="")

# session_id → {agent_id, session_id, group_id} 映射（内存，进程级）
_session_ctx_map: dict[str, dict[str, str]] = {}


# ── ASGI wrapper（仿 mcp_memory._AgentMCPWrapper）───────────────────────────


class _StepToolsMCPWrapper:
    """ASGI wrapper：从 SSE URL ?agent_id=&session_id=&group_id= 提取上下文，注入 tool。

    FastMCP SSE transport 流程：
      GET /sse?agent_id=X&session_id=Y&group_id=Z → 响应首个 SSE 事件含 mcp session_id
      POST /messages/?session_id=<mcp_sid> → 工具调用
    wrapper 在 SSE 响应流中找到 mcp session_id 后建立 session→上下文映射，
    POST 时按 mcp session_id 查映射并注入三个 ContextVar。
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
            agent_id = params.get("agent_id", "")
            session_id = params.get("session_id", "")
            group_id = params.get("group_id", "")

            async def _intercept_send(event: dict) -> None:
                if event["type"] == "http.response.body" and (agent_id or session_id):
                    body = event.get("body", b"").decode(errors="ignore")
                    for line in body.splitlines():
                        line = line.strip()
                        if "session_id=" in line:
                            # SSE 数据行格式: "data: /messages/?session_id=<uuid>"
                            sid = line.split("session_id=")[-1].strip()
                            if sid and sid not in _session_ctx_map:
                                _session_ctx_map[sid] = {
                                    "agent_id": agent_id,
                                    "session_id": session_id,
                                    "group_id": group_id,
                                }
                                logger.debug(
                                    "MCP step-tools session %s → agent=%s session=%s group=%s",
                                    sid, agent_id, session_id, group_id,
                                )
                await send(event)

            await self._app(scope, receive, _intercept_send)

        elif "/messages/" in path:
            mcp_session_id = params.get("session_id", "")
            ctx = _session_ctx_map.get(mcp_session_id, {})
            t_agent = _agent_id_ctx.set(ctx.get("agent_id", ""))
            t_sess = _session_id_ctx.set(ctx.get("session_id", ""))
            t_group = _group_id_ctx.set(ctx.get("group_id", ""))
            try:
                await self._app(scope, receive, send)
            finally:
                _agent_id_ctx.reset(t_agent)
                _session_id_ctx.reset(t_sess)
                _group_id_ctx.reset(t_group)

        else:
            await self._app(scope, receive, send)


# ── MCP app 构建 ─────────────────────────────────────────────────────────────


def _build_mcp_app() -> Any | None:
    if not _MCP_AVAILABLE:
        return None

    mcp = _FastMCP("agenthub-step-tools")

    @mcp.tool()
    async def task_complete(summary: str) -> dict[str, Any]:
        """宣告当前子任务完成。

        Worker 在完成所有工作后调用此工具。
        summary 应包含：做了什么、产物在哪、关键决策。
        Harness 收到后将 step 推进 VERIFYING → COMPLETED。
        """
        agent_id_str = _agent_id_ctx.get()
        session_id_str = _session_id_ctx.get()
        group_id_str = _group_id_ctx.get()

        if not agent_id_str:
            return {"status": "error", "detail": "agent_id not resolved (session not mapped)"}

        logger.info(
            "task_complete agent=%s session=%s group=%s summary=%.300s",
            agent_id_str, session_id_str, group_id_str, summary,
        )
        return {"status": "ok", "summary": summary}

    return _StepToolsMCPWrapper(mcp.sse_app())


_mcp_asgi = _build_mcp_app()


def get_mcp_step_tools_asgi() -> Any | None:
    """返回包了 _StepToolsMCPWrapper 的 ASGI app，供 main.py mount 使用。"""
    return _mcp_asgi
