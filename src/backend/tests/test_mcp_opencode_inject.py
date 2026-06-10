"""OpenCode MCP 注入单测（ADR-06 / RT-MCP §2.4）。

覆盖纯翻译函数 + 自包含配置写入；三路径（T-03）：stdio / remote / 空。
canonical 条目格式见 domain/mcp/rules.py::build_mcp_config_entry。
"""

from __future__ import annotations

import json

from app.domain.mcp.rules import build_mcp_config_entry
from app.infrastructure.llm.opencode_runtime import (
    _build_opencode_mcp,
    _entry_to_opencode,
    _write_opencode_config,
)


def test_entry_to_opencode_stdio_args_env() -> None:
    """stdio：command 合并为数组，env→environment，带 enabled。"""
    entry = build_mcp_config_entry(
        "fs", "stdio", {"command": "npx", "args": ["-y", "server-fs"], "env": {"TOKEN": "x"}}
    )
    name, value = _entry_to_opencode(entry)
    assert name == "fs"
    assert value == {
        "type": "local",
        "command": ["npx", "-y", "server-fs"],
        "enabled": True,
        "environment": {"TOKEN": "x"},
    }


def test_entry_to_opencode_stdio_minimal() -> None:
    """stdio 无 args/env：command 单元素数组，无 environment 键。"""
    entry = build_mcp_config_entry("bare", "stdio", {"command": "mcp-bare"})
    name, value = _entry_to_opencode(entry)
    assert name == "bare"
    assert value == {"type": "local", "command": ["mcp-bare"], "enabled": True}
    assert "environment" not in value


def test_entry_to_opencode_sse() -> None:
    """sse → opencode remote。"""
    entry = build_mcp_config_entry("remote-sse", "sse", {"url": "https://mcp.example/sse"})
    name, value = _entry_to_opencode(entry)
    assert name == "remote-sse"
    assert value == {"type": "remote", "url": "https://mcp.example/sse", "enabled": True}


def test_entry_to_opencode_http_headers() -> None:
    """streamable_http → remote，headers 透传。"""
    entry = build_mcp_config_entry(
        "remote-http", "streamable_http", {"url": "https://mcp.example/h", "headers": {"A": "b"}}
    )
    _name, value = _entry_to_opencode(entry)
    assert value["type"] == "remote"
    assert value["url"] == "https://mcp.example/h"
    assert value["headers"] == {"A": "b"}


def test_build_opencode_mcp_with_memory_and_binding() -> None:
    """记忆工具（remote）+ 绑定 server 同时进 mcp 块。"""
    entry = build_mcp_config_entry("fs", "stdio", {"command": "mcp-fs"})
    mcp = _build_opencode_mcp([entry], "http://mem.local/sse", "agent-123")
    assert mcp["agenthub-memory"] == {
        "type": "remote",
        "url": "http://mem.local/sse?agent_id=agent-123",
        "enabled": True,
    }
    assert mcp["fs"]["command"] == ["mcp-fs"]


def test_build_opencode_mcp_empty() -> None:
    """无记忆 URL 且无绑定 → 空 dict（调用方据此跳过 OPENCODE_CONFIG）。"""
    assert _build_opencode_mcp([], "", "") == {}
    assert _build_opencode_mcp(None, "", "agent-1") == {}


def test_write_opencode_config_self_contained() -> None:
    """写出文件含 mcp 段且为合法 JSON。

    现行行为（见 `_write_opencode_config` 注释「不注入 provider/model——CLI 读本地配置」）：
    配置只写 `{"mcp": ...}`，provider/apiKey 不再注入（OpenCode 读本地配置）。
    """
    entry = build_mcp_config_entry("fs", "stdio", {"command": "mcp-fs"})
    mcp = _build_opencode_mcp([entry], "", "")
    path = _write_opencode_config(mcp)
    assert path is not None
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    assert "provider" not in config  # provider 不再注入
    assert config["mcp"]["fs"]["command"] == ["mcp-fs"]


def test_write_opencode_config_remote_memory_entry() -> None:
    """远程记忆 MCP（sse）写成 remote 类型条目，配置仍自包含 mcp 段。"""
    mcp = _build_opencode_mcp(None, "http://mem/sse", "a1")
    path = _write_opencode_config(mcp)
    assert path is not None
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    assert "provider" not in config
    assert config["mcp"]["agenthub-memory"]["type"] == "remote"
