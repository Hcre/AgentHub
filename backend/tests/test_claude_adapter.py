"""ClaudeAdapter 单元测试：事件映射、重试、错误处理、prompt 构建。"""

from __future__ import annotations

import pytest

from app.domain.llm.protocol import (
    AgentRequest,
    MemoryContext,
    StreamEventType,
)
from app.infrastructure.llm.claude_adapter import (
    _build_system_prompt,
    _build_tool_definitions,
)

# ======================================================================
# _build_system_prompt 测试
# ======================================================================


class TestBuildSystemPrompt:
    @staticmethod
    def _make_request(**kwargs) -> AgentRequest:
        defaults = {
            "request_id": "test-001",
            "session_id": "00000000-0000-0000-0000-000000000001",
            "messages": [{"role": "user", "content": "hello"}],
        }
        defaults.update(kwargs)
        return AgentRequest(**defaults)

    def test_no_system_no_memory(self) -> None:
        req = self._make_request()
        result = _build_system_prompt(req)
        assert result == ""

    def test_system_prompt_only(self) -> None:
        req = self._make_request(system_prompt="You are a helpful assistant.")
        result = _build_system_prompt(req)
        assert result == "You are a helpful assistant."

    def test_memory_l2_l3_l4_merged(self) -> None:
        mem = MemoryContext(
            l1_working=[],
            l2_summary="User prefers concise answers.",
            l3_specs="Project: AgentHub",
            l4_rag="Relevant: adapter pattern docs",
        )
        req = self._make_request(system_prompt="Base prompt.", memory=mem)
        result = _build_system_prompt(req)

        assert "Base prompt." in result
        assert "Project: AgentHub" in result
        assert "User prefers concise answers." in result
        assert "Relevant: adapter pattern docs" in result
        # l3 排在 l2 前面（project context 优先于 summary）
        assert result.index("Project Context") < result.index("Conversation Summary")

    def test_partial_memory(self) -> None:
        mem = MemoryContext(l1_working=[], l4_rag="RAG result only")
        req = self._make_request(memory=mem)
        result = _build_system_prompt(req)
        assert "RAG result only" in result
        assert "Summary" not in result


# ======================================================================
# _build_tool_definitions 测试
# ======================================================================


class TestBuildToolDefinitions:
    def test_empty_tools(self) -> None:
        assert _build_tool_definitions([]) == []

    def test_tools_without_registry_returns_empty(self) -> None:
        # M3 前 ToolRegistry 不存在，应静默返回空
        result = _build_tool_definitions(["memory_retrieve", "git_diff"])
        assert result == []


# ======================================================================
# ClaudeAdapter 集成测试（需要 mock Anthropic client）
# ======================================================================


class TestClaudeAdapterStream:
    """使用 mock 模拟 Anthropic API 响应，验证事件映射。"""

    @pytest.mark.asyncio
    async def test_text_events(self) -> None:
        """验证纯文本流式响应产出 TEXT + DONE。"""
        from unittest.mock import AsyncMock, patch

        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        adapter = ClaudeAdapter(api_key="sk-test", model="test-model")

        # 构造 mock 事件序列
        events = _make_mock_text_events(["Hello", " world"])

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.__aiter__ = lambda self: _async_iter(events)

        with patch.object(adapter._client.messages, "stream", return_value=mock_stream):
            req = AgentRequest(
                request_id="test",
                session_id="00000000-0000-0000-0000-000000000001",
                messages=[{"role": "user", "content": "hi"}],
            )
            collected = [e async for e in adapter.stream(req)]

        types = [e.type for e in collected]
        assert StreamEventType.TEXT in types
        assert types[-1] == StreamEventType.DONE
        text_content = "".join(e.content for e in collected if e.type == StreamEventType.TEXT and e.content)
        assert text_content == "Hello world"

    @pytest.mark.asyncio
    async def test_tool_call_event(self) -> None:
        """验证 tool_use 块正确解析为 TOOL_CALL 事件。"""
        from unittest.mock import AsyncMock, patch

        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        adapter = ClaudeAdapter(api_key="sk-test", model="test-model")

        events = _make_mock_tool_events("memory_retrieve", '{"session_id": "abc"}')

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.__aiter__ = lambda self: _async_iter(events)

        with patch.object(adapter._client.messages, "stream", return_value=mock_stream):
            req = AgentRequest(
                request_id="test",
                session_id="00000000-0000-0000-0000-000000000001",
                messages=[{"role": "user", "content": "retrieve memory"}],
            )
            collected = [e async for e in adapter.stream(req)]

        tool_events = [e for e in collected if e.type == StreamEventType.TOOL_CALL]
        assert len(tool_events) == 1
        tc = tool_events[0].tool_call
        assert tc is not None
        assert tc.name == "memory_retrieve"
        assert tc.arguments == {"session_id": "abc"}

    @pytest.mark.asyncio
    async def test_error_yields_error_event(self) -> None:
        """非重试异常 → ERROR 事件。"""
        from unittest.mock import patch

        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        adapter = ClaudeAdapter(api_key="sk-test", model="test-model")

        with patch.object(
            adapter._client.messages, "stream", side_effect=ValueError("bad input")
        ):
            req = AgentRequest(
                request_id="test",
                session_id="00000000-0000-0000-0000-000000000001",
                messages=[{"role": "user", "content": "hi"}],
            )
            collected = [e async for e in adapter.stream(req)]

        assert len(collected) == 1
        assert collected[0].type == StreamEventType.ERROR
        assert "bad input" in (collected[0].content or "")

    @pytest.mark.asyncio
    async def test_token_usage_in_done(self) -> None:
        """验证 DONE 事件包含完整 token_usage。"""
        from unittest.mock import AsyncMock, patch

        from app.infrastructure.llm.claude_adapter import ClaudeAdapter

        adapter = ClaudeAdapter(api_key="sk-test", model="test-model")

        events = _make_mock_text_events(["Hi"], input_tokens=10, output_tokens=5)

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.__aiter__ = lambda self: _async_iter(events)

        with patch.object(adapter._client.messages, "stream", return_value=mock_stream):
            req = AgentRequest(
                request_id="test",
                session_id="00000000-0000-0000-0000-000000000001",
                messages=[{"role": "user", "content": "hi"}],
            )
            collected = [e async for e in adapter.stream(req)]

        done = [e for e in collected if e.type == StreamEventType.DONE][0]
        assert done.metadata["token_usage"] == {"input_tokens": 10, "output_tokens": 5}
        assert done.metadata["model"] == "test-model"


# ======================================================================
# Mock 事件工厂
# ======================================================================


async def _async_iter(items):
    for item in items:
        yield item


def _make_mock_text_events(
    texts: list[str],
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> list:
    """构造模拟 Anthropic SDK 事件序列（纯文本）。"""
    events = []

    # message_start
    msg_start = _mock_obj(
        type="message_start",
        message=_mock_obj(usage=_mock_obj(input_tokens=input_tokens)),
    )
    events.append(msg_start)

    # content_block_start (text)
    events.append(_mock_obj(
        type="content_block_start",
        content_block=_mock_obj(type="text"),
    ))

    # text deltas
    for t in texts:
        events.append(_mock_obj(
            type="content_block_delta",
            delta=_mock_obj(type="text_delta", text=t),
        ))

    # content_block_stop
    events.append(_mock_obj(type="content_block_stop"))

    # message_delta
    events.append(_mock_obj(
        type="message_delta",
        usage=_mock_obj(output_tokens=output_tokens),
        delta=_mock_obj(stop_reason="end_turn"),
    ))

    return events


def _make_mock_tool_events(tool_name: str, tool_input_json: str) -> list:
    """构造模拟 Anthropic SDK 事件序列（tool_use）。"""
    events = []

    # message_start
    events.append(_mock_obj(
        type="message_start",
        message=_mock_obj(usage=_mock_obj(input_tokens=15)),
    ))

    # content_block_start (tool_use)
    events.append(_mock_obj(
        type="content_block_start",
        content_block=_mock_obj(type="tool_use", name=tool_name, id="call_123"),
    ))

    # input_json_delta
    events.append(_mock_obj(
        type="content_block_delta",
        delta=_mock_obj(type="input_json_delta", partial_json=tool_input_json),
    ))

    # content_block_stop
    events.append(_mock_obj(type="content_block_stop"))

    # message_delta
    events.append(_mock_obj(
        type="message_delta",
        usage=_mock_obj(output_tokens=10),
        delta=_mock_obj(stop_reason="tool_use"),
    ))

    return events


def _mock_obj(**kwargs):
    """创建简单的 mock 对象，支持属性访问。"""

    class _Obj:
        pass

    obj = _Obj()
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj
