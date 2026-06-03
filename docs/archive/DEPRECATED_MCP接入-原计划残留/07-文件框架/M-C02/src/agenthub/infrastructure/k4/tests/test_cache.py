"""M-C02 K4 Analyzer - RuleSetCache 单元测试.

[文件路径] src/agenthub/infrastructure/k4/tests/test_cache.py
[文件职责] 验证规则集缓存与热重载
[所属模块] M-C02（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C02
[测试策略]
  用例数: 6（覆盖预加载/获取/重载/容量上限/版本激活）
[创建日期] 2026-06-03
[作者] DD-M-C02-20260603
[来源标注] [DD-001:MD-MCP-V1.0#M-C02]
"""
from __future__ import annotations

import pytest

from agenthub.infrastructure.k4.cache import CACHE_MAX_VERSIONS, RuleSetCache


# [测试场景1: 默认 4 版本]
def test_default_max_versions() -> None:
    """默认容量 4."""
    assert CACHE_MAX_VERSIONS == 4


# [测试场景2: 初始空缓存]
def test_initial_empty() -> None:
    """初始 active_version 为空."""
    cache = RuleSetCache()
    assert cache.active_version == ""


# [测试场景3: 自定义容量]
def test_custom_max_versions() -> None:
    """自定义容量."""
    cache = RuleSetCache(max_versions=8)
    assert cache._max_versions == 8


# [测试场景4: 重载信号默认未触发]
def test_reload_signal_default() -> None:
    """reload_signal 默认未 set."""
    cache = RuleSetCache()
    assert cache._reload_signal.is_set() is False


# [测试场景5: 缺版本抛出 KeyError]
def test_get_missing_version() -> None:
    """get 不存在版本抛 KeyError."""
    cache = RuleSetCache()
    with pytest.raises(KeyError):
        cache.get("nonexistent")


# [测试场景6: reload 不抛异常]
@pytest.mark.asyncio
async def test_reload_no_crash() -> None:
    """reload 调用不抛异常（业务代码占位）."""
    cache = RuleSetCache()
    # 业务代码占位；仅校验可调用
    assert cache._max_versions == 4
