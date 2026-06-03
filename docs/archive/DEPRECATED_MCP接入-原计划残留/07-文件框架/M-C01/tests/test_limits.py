"""M-C01 Limits 值对象测试场景."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

# TODO(impl): from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult


def test_limits_default_values_then_match_spec() -> None:
    """场景: 默认 Limits 字段符合 MD [DD-001:MD/M-C01] (cpu=100000/mem=512M/pids=32/fds=256/timeout=30)."""
    # TODO(impl): l = Limits()
    # TODO(impl): assert l.cpu_quota_us == 100_000
    # TODO(impl): assert l.memory_bytes == 512 * 1024 * 1024
    # TODO(impl): assert l.max_pids == 32
    # TODO(impl): assert l.max_fds == 256
    # TODO(impl): assert l.timeout_sec == 30
    ...


def test_limits_is_immutable_then_frozen() -> None:
    """场景: Limits 不可变 (frozen=True)."""
    # TODO(impl): l = Limits()
    # TODO(impl): with pytest.raises(ValidationError): l.cpu_quota_us = 999  # type: ignore[misc]
    ...


def test_limits_when_cpu_below_minimum_then_raise() -> None:
    """场景: cpu_quota_us < 1000 → ValidationError."""
    # TODO(impl): with pytest.raises(ValidationError): Limits(cpu_quota_us=500)
    ...


def test_limits_when_memory_below_16m_then_raise() -> None:
    """场景: memory_bytes < 16 MiB → ValidationError."""
    # TODO(impl): with pytest.raises(ValidationError): Limits(memory_bytes=1024 * 1024)
    ...


def test_limits_when_max_pids_exceeds_1024_then_raise() -> None:
    """场景: max_pids > 1024 → ValidationError."""
    # TODO(impl): with pytest.raises(ValidationError): Limits(max_pids=2048)
    ...


def test_limits_when_extra_field_then_raise() -> None:
    """场景: extra="forbid" 禁止未知字段."""
    # TODO(impl): with pytest.raises(ValidationError): Limits(unknown_field=1)  # type: ignore[call-arg]
    ...


def test_sandbox_result_when_construct_then_frozen() -> None:
    """场景: SandboxResult 不可变."""
    # TODO(impl): r = SandboxResult(exit_code=0, stdout=b"", stderr=b"", rss_peak=0, duration_ms=10, backend="linux_cgroup")
    # TODO(impl): with pytest.raises(ValidationError): r.exit_code = 1  # type: ignore[misc]
    ...


def test_sandbox_result_killed_reason_default_is_none() -> None:
    """场景: killed_reason 默认 None."""
    # TODO(impl): r = SandboxResult(exit_code=0, stdout=b"", stderr=b"", rss_peak=0, duration_ms=10, backend="docker")
    # TODO(impl): assert r.killed_reason is None
    ...
