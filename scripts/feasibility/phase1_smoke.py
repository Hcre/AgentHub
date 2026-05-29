"""Phase 1 Step 1 烟囱测试：长驻路径基本可用 + 多轮复用 PID。

目标（最小验证集，不替代完整集成测试）：
1. CLAUDE_CODE_LONG_RUNNING=1 时进入 V1 路径，spawn 一个长驻进程
2. 同 session_key 第二次请求不再 spawn，复用 PID
3. CLI 内部累积记忆：第二轮能回忆第一轮的信息

不跑完整 N=20 baseline（避免烧 token）；那一步在产品端真实场景里验。
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import uuid
from pathlib import Path

_backend = str(Path(__file__).resolve().parents[2] / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")
os.environ["CLAUDE_CODE_LONG_RUNNING"] = "1"

from app.domain.llm.protocol import AgentRequest, StreamEventType  # noqa: E402
from app.infrastructure.llm.claude_code_process_pool import (  # noqa: E402
    get_pool,
    shutdown_pool,
)
from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime  # noqa: E402


async def call_once(rt: ClaudeCodeRuntime, request: AgentRequest) -> tuple[str, dict]:
    """跑一次 stream() 收集 assistant 文本和最后的 DONE 元数据。"""
    text_chunks: list[str] = []
    done_meta: dict = {}
    async for evt in rt.stream(request):
        if evt.type == StreamEventType.TEXT and evt.content:
            text_chunks.append(evt.content)
        elif evt.type == StreamEventType.DONE:
            done_meta = evt.metadata or {}
        elif evt.type == StreamEventType.ERROR:
            print(f"[ERROR] {evt.content}")
    return "".join(text_chunks), done_meta


async def main() -> int:
    session_id = uuid.uuid4()
    rt = ClaudeCodeRuntime()
    pool = get_pool()

    # 用 group chat 标识 + 同 agent_id，让 session_key 在两轮请求间相同
    agent_id = uuid.uuid4()
    sp = "你是 Bob，一个简洁的助手。回答控制在 30 字以内。"

    print("=== Turn 1: 第一次请求，预期 spawn ===")
    req1 = AgentRequest(
        request_id="r1",
        session_id=session_id,
        messages=[{"role": "user", "content": "记住我的代号是 BLUE42。一句话确认。"}],
        system_prompt=sp,
        agent_id=agent_id,
        is_group_chat=True,
    )
    text1, _ = await call_once(rt, req1)
    print(f"  reply: {text1[:120]}")
    print(f"  pool size: {pool.size}")
    assert pool.size == 1, f"pool size 应为 1，实际 {pool.size}"
    handles = list(pool._handles.values())  # noqa: SLF001
    pid1 = handles[0].proc.pid
    print(f"  pid: {pid1}")

    print("\n=== Turn 2: 同 session_key 第二次请求，预期复用 PID ===")
    req2 = AgentRequest(
        request_id="r2",
        session_id=session_id,
        messages=[{"role": "user", "content": "我刚才的代号是什么？"}],
        system_prompt=sp,  # 同 sp，避免 drop+respawn
        agent_id=agent_id,
        is_group_chat=True,
    )
    text2, _ = await call_once(rt, req2)
    print(f"  reply: {text2[:120]}")
    print(f"  pool size: {pool.size}")
    pid2 = handles[0].proc.pid
    print(f"  pid: {pid2}")

    print("\n=== 校验 ===")
    pid_reused = pid1 == pid2
    remembers = "BLUE42" in text2.upper()
    print(f"  pid reused:    {'PASS' if pid_reused else 'FAIL'} (pid1={pid1} pid2={pid2})")
    print(f"  remembers code: {'PASS' if remembers else 'FAIL'} (text2 contains BLUE42 ? {remembers})")

    await shutdown_pool()
    print(f"  pool size after shutdown: {pool.size}")

    return 0 if (pid_reused and remembers) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
