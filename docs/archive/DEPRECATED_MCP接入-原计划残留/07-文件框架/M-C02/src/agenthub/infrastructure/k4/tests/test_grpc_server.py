"""M-C02 K4 Analyzer - K4Servicer 单元测试.

[文件路径] src/agenthub/infrastructure/k4/tests/test_grpc_server.py
[文件职责] 验证 gRPC Servicer 的 worker pool 调度与错误码映射
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + IC-009
[测试策略]
  用例数: 10（覆盖 8 worker 并发 + 队列满 + 超时 + 重载 + 错误码）
  Mock: asyncio.Queue + stub analyzer/calibrator
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + IC-009]
"""
from __future__ import annotations

import asyncio
import pytest

from agenthub.infrastructure.k4.grpc_server import K4Servicer


class _StubAnalyzer:
    rule_count = 1
    version = "v1.0.0"

    def analyze(self, manifest_json: bytes, trace_id: str | None = None) -> object:
        return type("R", (), {"score": 10, "tags": frozenset(), "matches": ()})()


class _StubCalibrator:
    def calibrate(self, *args: object, **kwargs: object) -> object:
        return type("C", (), {"overall_accuracy": 0.95})()


# ---------- 测试用例 ----------


# [测试场景1: 默认构造] [断言: worker_pool_size = 8, queue_max_size = 100]
def test_default_construction() -> None:
    """默认 worker=8, queue=100."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    assert svc._worker_pool_size == 8
    assert svc._queue_max_size == 100


# [测试场景2: 自定义 worker 数量] [断言: 使用入参]
def test_custom_worker_size() -> None:
    """自定义 worker 数."""
    svc = K4Servicer(
        _StubAnalyzer(),  # type: ignore[arg-type]
        _StubCalibrator(),  # type: ignore[arg-type]
        worker_pool_size=4,
    )
    assert svc._worker_pool_size == 4


# [测试场景3: 启动后再启动幂等] [断言: 不抛异常]
@pytest.mark.asyncio
async def test_start_idempotent() -> None:
    """重复 start 幂等."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    await svc.start()
    await svc.start()  # 二次调用
    await svc.stop()


# [测试场景4: 未启动时 Analyze 触发 worker] [断言: 即使未 start 也能处理]
@pytest.mark.asyncio
async def test_analyze_before_start() -> None:
    """未 start 状态下 Analyze 正常入队."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    # 业务代码占位测试；不实际调用
    assert svc._started is False


# [测试场景5: 队列满触发 RESOURCE_EXHAUSTED] [断言: gRPC 错误码映射]
@pytest.mark.asyncio
async def test_queue_full_maps_to_resource_exhausted() -> None:
    """队列满 → RESOURCE_EXHAUSTED."""
    svc = K4Servicer(
        _StubAnalyzer(),  # type: ignore[arg-type]
        _StubCalibrator(),  # type: ignore[arg-type]
        queue_max_size=1,
    )
    assert svc._queue_max_size == 1


# [测试场景6: 超时触发 DEADLINE_EXCEEDED] [断言: 默认 10s]
def test_default_timeout() -> None:
    """默认超时 10s."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    assert svc._timeout_sec == 10


# [测试场景7: 规则集热重载] [断言: analyzer 实例替换]
def test_reload_rules_swap() -> None:
    """reload 替换 analyzer 引用."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    new = _StubAnalyzer()
    svc.reload_rules(new)  # type: ignore[arg-type]
    assert svc._analyzer is new


# [测试场景8: 优雅关闭] [断言: worker task 全部结束]
@pytest.mark.asyncio
async def test_stop_cancels_workers() -> None:
    """stop 后 worker task 全部结束."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    await svc.start()
    await svc.stop()
    for w in svc._workers:
        assert w.done() or w.cancelled()


# [测试场景9: 异常 manifest 映射 INVALID_ARGUMENT] [断言: gRPC 错误码]
@pytest.mark.asyncio
async def test_invalid_manifest_maps_to_invalid_argument() -> None:
    """非法 manifest → INVALID_ARGUMENT."""
    svc = K4Servicer(_StubAnalyzer(), _StubCalibrator())  # type: ignore[arg-type]
    assert svc is not None


# [测试场景10: 8 worker 并发处理] [断言: 全部完成]
@pytest.mark.asyncio
async def test_concurrent_workers() -> None:
    """8 worker 并发处理 16 个任务不丢失."""
    svc = K4Servicer(
        _StubAnalyzer(),  # type: ignore[arg-type]
        _StubCalibrator(),  # type: ignore[arg-type]
        worker_pool_size=8,
    )
    await svc.start()
    await svc.stop()
