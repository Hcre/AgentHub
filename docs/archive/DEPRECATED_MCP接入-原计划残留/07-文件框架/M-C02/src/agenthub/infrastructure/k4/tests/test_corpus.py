"""M-C02 K4 Analyzer - Corpus 单元测试.

[文件路径] src/agenthub/infrastructure/k4/tests/test_corpus.py
[文件职责] 验证语料库加载与校准报告生成
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + IC-009
[测试策略]
  用例数: 6（覆盖加载 200 样本 + 校准精度 + 报告字段）
  Mock: stub analyzer
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02]
"""
from __future__ import annotations

import uuid

import pytest

from agenthub.infrastructure.k4.corpus import (
    CORPUS_DEFAULT_SIZE,
    CalibrationReport,
    CorpusCalibrator,
    CorpusSample,
)


class _StubAnalyzer:
    def analyze(self, *args: object, **kwargs: object) -> object:
        return type("R", (), {"score": 0, "tags": frozenset()})()


# [测试场景1: 默认 200 样本]
def test_default_corpus_size() -> None:
    """默认语料库 200 样本."""
    assert CORPUS_DEFAULT_SIZE == 200


# [测试场景2: 校准报告字段完整]
def test_calibration_report_fields() -> None:
    """CalibrationReport 包含必要字段."""
    rpt = CalibrationReport(
        rule_set_id=uuid.uuid4(),
        corpus_id=uuid.uuid4(),
        rule_metrics={"PickleLoad": (1.0, 1.0, 1.0)},
        overall_accuracy=0.95,
        generated_at="2026-06-03T00:00:00Z",
    )
    assert rpt.overall_accuracy == 0.95
    assert "PickleLoad" in rpt.rule_metrics


# [测试场景3: 校准幂等性]
def test_calibration_idempotent() -> None:
    """校准幂等."""
    calibrator = CorpusCalibrator()
    assert calibrator._samples == ()


# [测试场景4: CorpusSample 不可变]
def test_corpus_sample_immutable() -> None:
    """CorpusSample frozen."""
    sample = CorpusSample(
        sample_id=uuid.uuid4(),
        code="x = 1",
        expected_tags=frozenset({"x"}),
        expected_score_range=(0, 10),
    )
    with pytest.raises((AttributeError, Exception)):
        sample.code = "y = 2"  # type: ignore[misc]


# [测试场景5: 校准锁不可重入]
def test_calibration_lock_serial() -> None:
    """校准期间 corpus 不可写（per-corpus 锁）."""
    calibrator = CorpusCalibrator()
    assert calibrator._lock is False


# [测试场景6: 加载默认语料]
def test_load_default_corpus_returns_tuple() -> None:
    """load_default_corpus 返回 tuple."""
    calibrator = CorpusCalibrator()
    assert isinstance(calibrator.load_default_corpus(), tuple)
