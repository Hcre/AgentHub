"""ClaudeCodeRuntime 单元测试。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.llm.protocol import AgentRequest, StreamEventType
from app.infrastructure.llm.claude_code_runtime import ClaudeCodeRuntime


def _make_request(content: str = "hello") -> AgentRequest:
    return AgentRequest(
        request_id="test-001",
        session_id=uuid4(),
        messages=[{"role": "user", "content": content}],
    )


class TestParseLineUserEvent:
    def test_tool_result_success(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "call_001",
                    "content": "File created successfully.",
                }],
            },
        })
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_RESULT
        assert events[0].tool_result is not None
        assert events[0].tool_result.success is True
        assert events[0].tool_result.content == "File created successfully."

    def test_tool_result_error(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "call_002",
                    "content": "rm in '/tmp/x' was blocked.",
                    "is_error": True,
                }],
            },
        })
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_RESULT
        assert events[0].tool_result is not None
        assert events[0].tool_result.success is False
        assert "blocked" in (events[0].tool_result.error or "")


class TestParseLineResult:
    def test_result_with_permission_denials(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({
            "type": "result",
            "subtype": "error_max_turns",
            "is_error": True,
            "permission_denials": [
                {"tool_name": "Bash", "tool_use_id": "call_x", "tool_input": {"command": "rm -rf /tmp/x"}},
            ],
            "total_cost_usd": 0.05,
        })
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.DONE
        assert "permission_denials" in events[0].metadata
        assert events[0].metadata["is_error"] is True


class TestConstructor:
    def test_defaults(self) -> None:
        runtime = ClaudeCodeRuntime()
        assert runtime._api_key == ""
        assert runtime._model == ""
        assert runtime._permission_mode == "acceptEdits"
        assert runtime._max_turns == 10

    def test_full_config(self) -> None:
        runtime = ClaudeCodeRuntime(
            api_key="sk-test",
            model="claude-opus-4",
            base_url="https://api.example.com",
            permission_mode="bypassPermissions",
            max_turns=5,
            timeout=120,
        )
        assert runtime._api_key == "sk-test"
        assert runtime._model == "claude-opus-4"
        assert runtime._base_url == "https://api.example.com"
        assert runtime._permission_mode == "bypassPermissions"
        assert runtime._max_turns == 5
        assert runtime._timeout == 120


class TestBuildCmd:
    def test_includes_permission_and_max_turns(self) -> None:
        runtime = ClaudeCodeRuntime(permission_mode="acceptEdits", max_turns=5)
        req = _make_request("test")
        cmd = runtime._build_cmd(req, "session-123", resume=False)
        assert "--permission-mode" in cmd
        assert "--max-turns" in cmd
        cmd_str = " ".join(cmd)
        assert "acceptEdits" in cmd_str
        assert "5" in cmd_str

    def test_resume_flag(self) -> None:
        runtime = ClaudeCodeRuntime()
        req = _make_request()
        cmd = runtime._build_cmd(req, "session-123", resume=True)
        assert "--resume" in cmd
        assert "session-123" in cmd


class TestBuildEnv:
    def test_inherits_os_environ(self) -> None:
        import os
        runtime = ClaudeCodeRuntime()
        env = runtime._build_env()
        assert "PATH" in env

    def test_sets_anthropic_vars(self) -> None:
        runtime = ClaudeCodeRuntime(
            api_key="sk-test",
            model="claude-opus-4",
            base_url="https://api.example.com",
        )
        env = runtime._build_env()
        assert env["ANTHROPIC_API_KEY"] == "sk-test"
        assert env["ANTHROPIC_MODEL"] == "claude-opus-4"
        assert env["ANTHROPIC_BASE_URL"] == "https://api.example.com"


class TestParseLineText:
    def test_assistant_text(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "hello world"}],
                "usage": {},
            },
        })
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TEXT
        assert events[0].content == "hello world"

    def test_assistant_tool_use(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "call_123",
                    "name": "read_file",
                    "input": {"path": "/tmp/test.py"},
                }],
                "usage": {},
            },
        })
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_CALL
        assert events[0].tool_call is not None
        assert events[0].tool_call.name == "read_file"

    def test_result_done(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({
            "type": "result",
            "subtype": "success",
            "duration_ms": 2000,
            "total_cost_usd": 0.05,
        })
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.DONE
        assert events[0].metadata["total_cost_usd"] == 0.05

    def test_system_event_ignored(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps({"type": "system", "subtype": "init"})
        events = runtime._parse_line(line, 0)
        assert events == []

    def test_invalid_json(self) -> None:
        runtime = ClaudeCodeRuntime()
        events = runtime._parse_line("not json", 0)
        assert events == []


class TestExtractPrompt:
    def test_extracts_last_user(self) -> None:
        req = _make_request("test prompt")
        assert ClaudeCodeRuntime._extract_prompt(req) == "test prompt"

    def test_empty_messages(self) -> None:
        req = AgentRequest(
            request_id="test",
            session_id=uuid4(),
            messages=[],
        )
        assert ClaudeCodeRuntime._extract_prompt(req) == ""


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_no_process(self) -> None:
        runtime = ClaudeCodeRuntime()
        await runtime.stop()  # should not raise
