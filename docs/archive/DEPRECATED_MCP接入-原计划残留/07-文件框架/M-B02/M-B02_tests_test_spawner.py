"""M-B02 ProcessSpawner 单元测试.

[文件路径] src/agenthub/application/pool/tests/test_spawner.py
[文件职责] 进程工厂测试
[所属模块] M-B02
[关联设计规范] FS-006 / MD-MCP-M-B02
[测试策略]
  范围: 单元（mock asyncio subprocess）
  用例数: 8
  Mock: asyncio.create_subprocess_exec

测试场景:
  - test_create_when_cmd_valid_then_return_process
      断言: 返回 Process 且 pid > 0
  - test_create_when_cmd_not_list_then_raise_value_error
      断言: cmd 为 str 时 raise ValueError（防命令注入 [TD:S-026]）
  - test_create_when_subprocess_fails_then_retry_3_times
      断言: 失败重试 3 次
  - test_create_when_retry_exhausted_then_raise_spawn_failed
      断言: 3 次后 raise SpawnFailedError
  - test_create_when_env_includes_ws_mcp_trace_id
      断言: 子进程 env 包含 WS_ID / MCP_ID / TRACE_ID
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7 测试规范
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:FS-006 + MD-MCP-M-B02 + AR洞察-2]
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

# 业务测试由开发工程师实现
__all__: list[str] = []
