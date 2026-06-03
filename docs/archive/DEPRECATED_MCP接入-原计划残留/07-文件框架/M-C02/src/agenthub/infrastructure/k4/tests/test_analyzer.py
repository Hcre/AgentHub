"""M-C02 K4 Analyzer - ASTAnalyzer 单元测试.

[文件路径] src/agenthub/infrastructure/k4/tests/test_analyzer.py
[文件职责] 验证 ASTAnalyzer 模板方法骨架与四步流程
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02 + IC-009
[测试策略]
  用例数: 8（覆盖模板方法 4 步骤 × 正常/异常 + 版本注入 + 不可实例化）
  Mock: 注入 stub Rule / 注入坏 manifest
  覆盖率: 行 ≥ 90%
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 测试策略]
"""
from __future__ import annotations

import ast
import pytest

from agenthub.infrastructure.k4.analyzer import (
    ASTAnalyzer,
    MatchResult,
    ScoreResult,
)


class _StubRule:
    """测试用 stub Rule（不依赖 protobuf）."""

    name = "Stub"
    version = "1.0"
    severity = 50

    def __init__(self, match_value: MatchResult | None) -> None:
        self._match_value = match_value

    def match(self, node: ast.AST) -> MatchResult | None:
        return self._match_value

    def matches(self, tree: ast.AST) -> list[MatchResult]:
        return [self._match_value] if self._match_value else []


class _ConcreteAnalyzer(ASTAnalyzer):
    """测试用具体子类."""

    def _parse(self, manifest_json: bytes) -> ast.Module:
        return ast.parse(manifest_json.decode("utf-8"))

    def _walk(self, tree: ast.Module) -> list[MatchResult]:
        out: list[MatchResult] = []
        for rule in self._rules:
            result = rule.match(tree)  # type: ignore[attr-defined]
            if result is not None:
                out.append(result)
            walk_result = rule.matches(tree)  # type: ignore[attr-defined]
            out.extend(walk_result)
        return out

    def _score(self, matches: list[MatchResult]) -> int:
        return min(sum(m.severity for m in matches), 100)

    def _tag(self, score: int) -> frozenset[str]:
        if score >= 70:
            return frozenset({"high_risk"})
        if score >= 40:
            return frozenset({"warning"})
        return frozenset()


# ---------- 测试用例 ----------


# [测试场景1: 正常流程] [断言: 返回 ScoreResult 且 trace_id 注入]
def test_analyze_normal_flow() -> None:
    """正常 manifest 走完模板四步."""
    rule = _StubRule(MatchResult("Stub", 30, 1, 0, "x"))
    analyzer = _ConcreteAnalyzer([rule], version="v1.0.0")
    result = analyzer.analyze(b"x = 1", trace_id="t-001")
    assert isinstance(result, ScoreResult)
    assert result.trace_id == "t-001"
    assert result.rule_set_version == "v1.0.0"


# [测试场景2: 高分阈值] [断言: score >= 70 → is_high_risk == True]
def test_high_risk_threshold() -> None:
    """高分命中 → high_risk 标签."""
    rule = _StubRule(MatchResult("Stub", 80, 1, 0, "x"))
    analyzer = _ConcreteAnalyzer([rule], version="v1.0.0")
    result = analyzer.analyze(b"x = 1")
    assert result.is_high_risk is True
    assert "high_risk" in result.tags


# [测试场景3: 警告阈值] [断言: 40 <= score < 70 → is_warning == True]
def test_warning_threshold() -> None:
    """中分命中 → warning 标签."""
    rule = _StubRule(MatchResult("Stub", 50, 1, 0, "x"))
    analyzer = _ConcreteAnalyzer([rule], version="v1.0.0")
    result = analyzer.analyze(b"x = 1")
    assert result.is_warning is True
    assert "warning" in result.tags


# [测试场景4: 缺省 trace_id 自动生成] [断言: trace_id 为 UUID 格式]
def test_default_trace_id() -> None:
    """未传 trace_id 时自动生成."""
    rule = _StubRule(None)
    analyzer = _ConcreteAnalyzer([rule], version="v1.0.0")
    result = analyzer.analyze(b"x = 1")
    assert len(result.trace_id) == 36


# [测试场景5: 语法错误 manifest] [断言: 抛出 SyntaxError → K4InvalidArgument]
def test_invalid_syntax_manifest() -> None:
    """不可解析 manifest 抛 SyntaxError."""
    rule = _StubRule(None)
    analyzer = _ConcreteAnalyzer([rule], version="v1.0.0")
    with pytest.raises(SyntaxError):
        analyzer.analyze(b"def broken(:\n  pass")


# [测试场景6: 空 manifest] [断言: score = 0, tags = empty]
def test_empty_manifest() -> None:
    """空 manifest 评分 0."""
    rule = _StubRule(None)
    analyzer = _ConcreteAnalyzer([rule], version="v1.0.0")
    result = analyzer.analyze(b"")
    assert result.score == 0
    assert result.tags == frozenset()


# [测试场景7: 抽象基类不可直接实例化] [断言: TypeError]
def test_abstract_instantiation() -> None:
    """ASTAnalyzer 不可直接实例化."""
    with pytest.raises(TypeError):
        ASTAnalyzer(rules=[], version="v1.0.0")  # type: ignore[abstract]


# [测试场景8: 多命中按 severity 降序] [断言: matches 列表已排序]
def test_matches_sorted_by_severity_desc() -> None:
    """命中按严重度降序排序."""
    r1 = _StubRule(MatchResult("L", 20, 1, 0, "x"))
    r2 = _StubRule(MatchResult("H", 80, 1, 0, "x"))
    analyzer = _ConcreteAnalyzer([r1, r2], version="v1.0.0")
    result = analyzer.analyze(b"x = 1")
    assert result.matches[0].severity >= result.matches[-1].severity
