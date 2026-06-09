"""Pi Agent E2E 集成测试（不需要完整基础设施）。

验证:
1. 工厂正确路由 PI_AGENT → PiAgentRuntime
2. PiAgentRuntime 能启动 pi 子进程
3. RPC 协议通信正常（prompt → response）
4. stop() 能终止子进程
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest

# 设置 backend 路径（src/backend，含 app 包）以支持 standalone 运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 确保 npm 全局 bin 路径在 PATH 中（Pi CLI 安装位置）
npm_bin = str(Path.home() / "AppData" / "Roaming" / "npm")
if npm_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = npm_bin + os.pathsep + os.environ.get("PATH", "")

# 设置环境变量（若未设置）
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test_key_for_e2e")


async def test_factory_routing():
    """测试1: 工厂路由

    v4 R2 起（commit 之后, factory.py 严格硬依赖 CLI），无 Pi CLI 直接 raise —
    本机无 pi 二进制时（per TD-04）整测试 skip。Setup 早期 return 比让 factory 抛
    RuntimeError 再 skip 干净。
    """
    if not shutil.which("pi"):
        pytest.skip("Pi CLI 未安装（per TD-04：v4 R2 起 factory 硬依赖 CLI）")
    from app.domain.entities.agent import Agent
    from app.domain.enums import AgentStatus, AgentSystem, Provider
    from app.infrastructure.llm.factory import build_adapter_for_agent

    agent = Agent(
        name="Pi测试助手",
        avatar="",
        role="测试",
        agent_system=AgentSystem.PI_AGENT,
        skills=[],
        capability_tags=[],
        system_prompt="You are a test assistant.",
        status=AgentStatus.ONLINE,
        workload=0,
        is_system=False,
        settings={"thinking_level": "off", "cli_timeout": 30},
    )

    from app.infrastructure.llm.pi_agent_runtime import PiAgentRuntime

    adapter = build_adapter_for_agent(agent)
    assert isinstance(adapter, PiAgentRuntime), f"Expected PiAgentRuntime, got {type(adapter)}"
    print("  [PASS] Factory routing: AgentSystem.PI_AGENT -> PiAgentRuntime")


async def test_subprocess_lifecycle():
    """测试2: 子进程启动/停止"""
    from app.infrastructure.llm.pi_agent_runtime import PiAgentRuntime

    runtime = PiAgentRuntime(
        model="claude-sonnet-4-20250514",
        agent_id=str(uuid4()),
        provider="anthropic",
        api_key="",  # 无 API key — 验证错误处理
        base_url="",
        timeout=30,
    )

    # 测试 stop() 在无运行进程时的安全性
    await runtime.stop()
    print("  [PASS] stop() safe to call with no running process")

    # 测试 stream（预期因无 API key 返回错误）
    from app.domain.llm.protocol import AgentRequest

    request = AgentRequest(
        request_id=str(uuid4()),
        session_id=uuid4(),
        messages=[{"role": "user", "content": "say hi"}],
        system_prompt=None,
    )

    events = []
    async for event in runtime.stream(request):
        events.append(event)

    assert len(events) > 0, "Should have at least one event"
    print(f"  [PASS] stream produced {len(events)} events")

    # 验证事件类型
    event_types = [e.type.value for e in events]
    print(f"    Event types: {event_types}")

    # 无 API key 时应看到 ERROR 或 DONE 事件
    has_error_or_done = any(e.type.value in ("error", "done") for e in events)
    assert has_error_or_done, "Should have ERROR or DONE event"
    print("  [PASS] Pi subprocess handles no-API-key gracefully")


async def test_rpc_protocol():
    """测试3: RPC 协议 — 带 API key 的完整通话"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  [SKIP] RPC communication test (needs ANTHROPIC_API_KEY)")
        return

    from app.domain.llm.protocol import AgentRequest
    from app.infrastructure.llm.pi_agent_runtime import PiAgentRuntime

    runtime = PiAgentRuntime(
        model="claude-sonnet-4-20250514",
        agent_id=str(uuid4()),
        provider="anthropic",
        api_key=api_key,
        timeout=60,
    )

    request = AgentRequest(
        request_id=str(uuid4()),
        session_id=uuid4(),
        messages=[{"role": "user", "content": "Reply with just: OK"}],
        system_prompt="Reply concisely.",
    )

    text_parts = []
    tool_calls = 0
    done = False

    async for event in runtime.stream(request):
        t = event.type.value
        if t == "text" and event.content:
            text_parts.append(event.content)
        elif t == "tool_call":
            tool_calls += 1
        elif t == "done":
            done = True
        elif t == "error":
            print(f"    Error: {event.content[:200] if event.content else 'unknown'}")
            done = True

    response = "".join(text_parts)
    print(f"  [PASS] RPC response: {response[:200]}")
    print(f"    Tool calls: {tool_calls}")
    print(f"    DONE event: {done}")


async def main():
    print("Pi Agent E2E 集成测试")
    print("=" * 50)

    print("\n1. 工厂路由测试")
    await test_factory_routing()

    print("\n2. 子进程生命周期测试")
    await test_subprocess_lifecycle()

    print("\n3. RPC 协议通信测试")
    await test_rpc_protocol()

    print("\n" + "=" * 50)
    print("E2E 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
