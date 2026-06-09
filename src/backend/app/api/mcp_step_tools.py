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

# ── ASGI wrapper（仿 mcp_memory._AgentMCPWrapper）───────────────────────────


class _StepToolsMCPWrapper:
    """ASGI wrapper：从 SSE URL ?agent_id=&session_id=&group_id= 提取上下文，注入 tool。

    **关键**：在 GET /sse 分支 set ContextVar，而不是 POST /messages 分支。
    MCP SDK 的 `app.run()`（工具派发循环）在 GET /sse 处理协程里 inline 运行——
    所有工具调用都在这条 SSE 连接的 async 任务内执行。ContextVar 在该任务内 set 后，
    对任务内 await 的一切（含工具）可见。POST /messages 只是把消息写进流、在另一个任务，
    在那 set ContextVar 跨不到工具执行处（此前 not resolved 的根因）。
    一条 SSE 连接对应一个 worker，URL 自带其 agent_id，天然隔离、并发安全。
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
            # 工具在本 GET 协程内派发 → 在此 set ContextVar，工具可见。
            t_agent = _agent_id_ctx.set(params.get("agent_id", ""))
            t_sess = _session_id_ctx.set(params.get("session_id", ""))
            t_group = _group_id_ctx.set(params.get("group_id", ""))
            logger.info(
                "MCP step-tools SSE 连接 agent=%s session=%s group=%s",
                params.get("agent_id", ""), params.get("session_id", ""), params.get("group_id", ""),
            )
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
