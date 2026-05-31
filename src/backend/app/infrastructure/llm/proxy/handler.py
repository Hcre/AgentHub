"""ProxyHandler：透明反向代理——鉴权适配 + URL 路由 + 流式转发。

CLI 子进程的 ANTHROPIC_BASE_URL 指向本代理，代理解析 agent_id 后：
  1. 查数据库获取 Agent 配置
  2. 解密真实 API Key
  3. 替换 auth header 为 Provider 真实凭证
  4. 拼接目标 URL → 流式转发请求和响应
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.security import decrypt_secret

logger = logging.getLogger(__name__)

_HOP_BY_HOP_HEADERS = frozenset(
    {
        "host",
        "connection",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    }
)


class ProxyHandler:
    """无状态处理器。client 由 lifespan 注入，每次请求由路由层传入。"""

    def __init__(self, agent_repo):
        self._agent_repo = agent_repo

    async def handle(
        self,
        agent_id: str,
        path: str,
        request: Request,
        client: httpx.AsyncClient,
    ) -> Response:
        # 1. 查 Agent
        try:
            uid = UUID(agent_id)
        except ValueError:
            return JSONResponse({"error": "invalid agent_id"}, status_code=400)

        agent = await self._agent_repo.get_by_id(uid)
        if not agent:
            return JSONResponse({"error": "agent not found"}, status_code=404)

        # 2. 解密 API Key
        real_key = decrypt_secret(agent.api_key_encrypted)
        if not real_key:
            return JSONResponse({"error": "agent has no api_key"}, status_code=400)

        # 3. HEAD 请求直接返回 200（CLI 连通性检查）
        if request.method == "HEAD":
            return Response(status_code=200)

        # 4. 拼接目标 URL
        base = (agent.base_url or "").rstrip("/")
        if not base:
            return JSONResponse({"error": "agent has no base_url"}, status_code=400)
        target_url = f"{base}/{path}"
        if request.url.query:
            target_url += (
                f"?{request.url.query.decode()}"
                if isinstance(request.url.query, bytes)
                else f"?{request.url.query}"
            )

        logger.info("proxy %s %s → %s", request.method, agent_id, target_url[:120])

        # 4. 构建转发 headers（过滤 hop-by-hop，替换占位 key）
        forward_headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in _HOP_BY_HOP_HEADERS
        }
        forward_headers["x-api-key"] = real_key

        # 5. 处理 body — 非 Anthropic 提供商过滤 system 消息
        body = await request.body()
        if body and "deepseek" in (agent.base_url or "").lower():
            try:
                data = json.loads(body)
                msgs = data.get("messages", [])
                if msgs:
                    data["messages"] = [m for m in msgs if m.get("role") != "system"]
                    body = json.dumps(data).encode()
                    forward_headers["content-length"] = str(len(body))
            except (json.JSONDecodeError, ValueError):
                pass

        # 6. 流式转发
        upstream = await client.send(
            client.build_request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
            ),
            stream=True,
        )

        response_headers = {
            k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS
        }

        if upstream.status_code >= 400:
            logger.warning(
                "proxy upstream error agent=%s status=%d",
                agent_id,
                upstream.status_code,
            )

        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=response_headers,
        )
