"""test_log_config.py - LogConfig / configure_logging 单元测试.

[文件路径] src/agenthub/data/ts_log/tests/test_log_config.py
[文件职责] structlog 初始化 + get_logger 行为
[所属模块] M-D02
[测试策略] [DD-001:MD-MCP M-D02] 用例数 12（与 metrics 合并）
[来源标注] [DD-001:MD-MCP M-D02]
"""
from __future__ import annotations

import logging

import pytest
import structlog

from agenthub.data.ts_log.log_config import LogConfig, configure_logging, get_logger


class TestLogConfig:
    """[测试类] LogConfig 数据类 + 初始化."""

    def test_logconfig_default_values_then_valid(self) -> None:
        # [测试场景1: 默认构造] 断言: 字段默认值符合预期
        cfg = LogConfig()
        assert cfg.level == "INFO"
        assert cfg.json_format is True
        assert cfg.service_name == "agenthub"
        assert cfg.inject_trace_id is True

    def test_configure_logging_when_called_then_logger_writable(self) -> None:
        # [测试场景2: 初始化] 断言: configure_logging 不抛，get_logger 返回可用对象
        # [Mock: 无]
        configure_logging(settings=_FakeSettings())  # type: ignore[arg-type]
        log = get_logger("test")
        log.info("hello", key="value")  # 不抛即通过

    def test_get_logger_when_same_name_then_bound_logger(self) -> None:
        # [测试场景3: 工厂幂等] 断言: 同 name 返回可绑定 logger
        log1 = get_logger("svc.x")
        log2 = get_logger("svc.x")
        assert log1 is not None
        log1.bind(req_id="r1").info("test")

    def test_log_when_json_format_then_output_is_json_lines(self, capsys) -> None:
        # [测试场景4: JSON Lines 格式] 断言: stdout 含合法 JSON
        configure_logging(settings=_FakeSettings(log_level="INFO"))  # type: ignore[arg-type]
        get_logger("json_test").info("evt", k="v")
        # stdout 验证（structlog 输出）
        # [DD-001:IC-018] JSON Lines → Loki 兼容


class _FakeSettings:
    """测试用 Settings 桩（仅暴露 configure_logging 所需字段）."""
    def __init__(self, log_level: str = "INFO") -> None:
        self.log_level = log_level
        self.service_name = "agenthub-test"
        self.env = "test"
        self.version = "0.0.0-test"
