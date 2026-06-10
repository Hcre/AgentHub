"""ClaudeCodeRuntime 单元测试。"""

from __future__ import annotations

import json
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
        line = json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_001",
                            "content": "File created successfully.",
                        }
                    ],
                },
            }
        )
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_RESULT
        assert events[0].tool_result is not None
        assert events[0].tool_result.success is True
        assert events[0].tool_result.content == "File created successfully."

    def test_tool_result_error(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_002",
                            "content": "rm in '/tmp/x' was blocked.",
                            "is_error": True,
                        }
                    ],
                },
            }
        )
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_RESULT
        assert events[0].tool_result is not None
        assert events[0].tool_result.success is False
        assert "blocked" in (events[0].tool_result.error or "")


class TestParseLineResult:
    def test_result_with_permission_denials(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps(
            {
                "type": "result",
                "subtype": "error_max_turns",
                "is_error": True,
                "permission_denials": [
                    {
                        "tool_name": "Bash",
                        "tool_use_id": "call_x",
                        "tool_input": {"command": "rm -rf /tmp/x"},
                    },
                ],
                "total_cost_usd": 0.05,
            }
        )
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.DONE
        assert "permission_denials" in events[0].metadata
        assert events[0].metadata["is_error"] is True


class TestConstructor:
    def test_defaults(self) -> None:
        runtime = ClaudeCodeRuntime()
        assert runtime._model == ""
        assert runtime._proxy_url == ""
        assert runtime._permission_mode == "bypassPermissions"
        assert runtime._max_turns == 10

    def test_full_config(self) -> None:
        runtime = ClaudeCodeRuntime(
            model="claude-opus-4",
            agent_id="test-agent-id",
            proxy_base="http://127.0.0.1:8000",
            permission_mode="bypassPermissions",
            max_turns=5,
            timeout=120,
        )
        assert runtime._model == "claude-opus-4"
        assert "test-agent-id" in runtime._proxy_url
        assert runtime._permission_mode == "bypassPermissions"
        assert runtime._max_turns == 5
        assert runtime._timeout == 120

    def test_global_mode_no_proxy(self) -> None:
        runtime = ClaudeCodeRuntime(model="claude-sonnet-4")
        assert runtime._proxy_url == ""


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
        runtime = ClaudeCodeRuntime()
        env = runtime._build_env()
        assert "PATH" in env

    def test_proxy_mode_builds_proxy_url_not_env(self) -> None:
        """代理模式：proxy 经 `_proxy_url`（CLI 配置/命令）注入，而非 env 变量。

        现行行为（见 `_build_env` 注释「不注入 provider/model——CLI 读本地配置」）：
        `_build_env` 仅透传 os.environ，不再写 ANTHROPIC_API_KEY/MODEL/BASE_URL。
        proxy 目标改由构造期算出的 `_proxy_url` 承载。
        """
        runtime = ClaudeCodeRuntime(
            model="claude-opus-4",
            agent_id="agent-001",
            proxy_base="http://127.0.0.1:8000",
        )
        assert runtime._proxy_url == "http://127.0.0.1:8000/proxy/agents/agent-001"
        env = runtime._build_env()
        # env 不再被注入代理凭证（旧行为已移除）
        assert env.get("ANTHROPIC_API_KEY") != "agenthub-proxy"

    def test_global_mode_preserves_shell_env(self) -> None:
        """全局模式：`_build_env` 透传 os.environ，不覆盖 ANTHROPIC_* 变量。"""
        runtime = ClaudeCodeRuntime(model="claude-sonnet-4")
        assert runtime._proxy_url == ""  # 无 agent_id/proxy_base → 不走代理
        env = runtime._build_env()
        assert "PATH" in env  # 透传 shell 环境
        assert env.get("ANTHROPIC_API_KEY") != "agenthub-proxy"


class TestParseLineText:
    def test_assistant_text(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "hello world"}],
                    "usage": {},
                },
            }
        )
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TEXT
        assert events[0].content == "hello world"

    def test_assistant_tool_use(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_123",
                            "name": "read_file",
                            "input": {"path": "/tmp/test.py"},
                        }
                    ],
                    "usage": {},
                },
            }
        )
        events = runtime._parse_line(line, 0)
        assert len(events) == 1
        assert events[0].type == StreamEventType.TOOL_CALL
        assert events[0].tool_call is not None
        assert events[0].tool_call.name == "read_file"

    def test_result_done(self) -> None:
        runtime = ClaudeCodeRuntime()
        line = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "duration_ms": 2000,
                "total_cost_usd": 0.05,
            }
        )
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


class TestDeltaSplit:
    """Phase 1 拆 delta：AgentRequest.group_delta_text 处理。"""

    def test_v0_merge_no_delta_keeps_sp(self) -> None:
        req = AgentRequest(
            request_id="r",
            session_id=uuid4(),
            messages=[{"role": "user", "content": "hi"}],
            system_prompt="你是 Bob",
            is_group_chat=True,
            agent_id=uuid4(),
        )
        m = ClaudeCodeRuntime._merge_delta_into_system_prompt_v0(req)
        assert m.system_prompt == "你是 Bob"
        assert m.group_delta_text is None

    def test_v0_merge_with_delta(self) -> None:
        req = AgentRequest(
            request_id="r",
            session_id=uuid4(),
            messages=[{"role": "user", "content": "hi"}],
            system_prompt="你是 Bob\n\n契约...",
            group_delta_text="Alice: 大家好",
            is_group_chat=True,
            agent_id=uuid4(),
        )
        m = ClaudeCodeRuntime._merge_delta_into_system_prompt_v0(req)
        assert "Alice: 大家好" in m.system_prompt
        assert m.system_prompt.endswith("Alice: 大家好")
        assert m.group_delta_text is None

    def test_v1_user_prompt_no_delta(self) -> None:
        req = AgentRequest(
            request_id="r",
            session_id=uuid4(),
            messages=[{"role": "user", "content": "hello"}],
            system_prompt="sp",
        )
        assert ClaudeCodeRuntime._build_v1_user_prompt(req) == "hello"

    def test_v1_user_prompt_with_delta(self) -> None:
        req = AgentRequest(
            request_id="r",
            session_id=uuid4(),
            messages=[{"role": "user", "content": "回复请"}],
            system_prompt="sp",
            group_delta_text="Alice: 大家好",
            is_group_chat=True,
            agent_id=uuid4(),
        )
        out = ClaudeCodeRuntime._build_v1_user_prompt(req)
        assert "Alice: 大家好" in out
        assert "回复请" in out
        # delta 在 trigger 之前
        assert out.index("Alice") < out.index("回复请")


class TestComputeSessionKey:
    """V1 长驻 + V0 短驻共用：私聊 = session_id，群聊 = uuid5(session_id:agent_id)。"""

    def test_private_chat_uses_session_id(self) -> None:
        sid = uuid4()
        req = AgentRequest(
            request_id="r",
            session_id=sid,
            messages=[{"role": "user", "content": "hi"}],
            is_group_chat=False,
        )
        assert ClaudeCodeRuntime._compute_session_key(req) == str(sid)

    def test_group_chat_deterministic_uuid5(self) -> None:
        sid = uuid4()
        aid = uuid4()
        req = AgentRequest(
            request_id="r",
            session_id=sid,
            messages=[{"role": "user", "content": "hi"}],
            is_group_chat=True,
            agent_id=aid,
        )
        k1 = ClaudeCodeRuntime._compute_session_key(req)
        k2 = ClaudeCodeRuntime._compute_session_key(req)
        assert k1 == k2  # 同输入相同输出
        # 不同 agent_id 不同 key
        req2 = req.model_copy(update={"agent_id": uuid4()})
        assert ClaudeCodeRuntime._compute_session_key(req2) != k1
