"""Prometheus 指标注册与暴露.

[文件路径] src/agenthub/data/ts_log/metrics.py
[文件职责] Prometheus Registry + 自定义 collector 的封装
[所属模块] M-D02（来自DD-001）
[关联设计规范] FS-020 / MD-MCP M-D02 / IC-018
[功能描述]
  功能1: 集中创建 Counter / Gauge / Histogram 三类指标
  功能2: 暴露 /metrics 端点供 Prometheus server 15s 拉取
  功能3: 自定义 collector 用于采集运行时业务指标（如 pool_size）
[输入输出]
  输入: 指标名称 + label 列表 + help 文本
  输出: prometheus_client.Counter / Gauge / Histogram 实例
[依赖关系]
  依赖文件: agenthub.core.config（获取 service_name / env 标签）
  被依赖文件: 所有业务模块（通过 get_counter / get_gauge 注入指标）
[注意事项]
  注意1: 同一 name + labels 重复注册会抛 Duplicated timeseries，需复用实例
  注意2: label 基数必须可控，避免高基数 label（如 trace_id 不可作为 label）
  注意3: PromExportError 降级到本地 in-memory buffer（5min 滚动）
  注意4: /metrics 端点为文本格式，UTF-8 编码，Content-Type: text/plain
[代码风格] 遵循CS-MCP §1（Google docstring + mypy strict）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D02 - 初始框架
[作者] DD-M-D02-20260603
[来源标注] [DD-001:FS-020 / MD-MCP M-D02 / IC-018]
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

if TYPE_CHECKING:
    from agenthub.core.config import Settings


# 模块级 Registry 单例（Prom client 内部加锁，线程安全）
_REGISTRY: CollectorRegistry = CollectorRegistry(auto_describe=True)


class MetricsRegistry:
    """[类名] MetricsRegistry.

    [职责] 集中管理 Prometheus 指标注册与暴露.
    [关联设计规范] MD-MCP M-D02（MetricsRegistry 类设计）
    [属性]
      属性1: registry CollectorRegistry - prom 客户端注册表
      属性2: default_labels list[str] - 注入 service / env / version
    [方法列表]
      方法1: counter(name, labels) -> Counter - 创建/获取计数器
      方法2: gauge(name, labels) -> Gauge - 创建/获取仪表
      方法3: histogram(name, labels, buckets) -> Histogram - 创建/获取直方图
      方法4: render() -> bytes - 渲染 exposition format
    [异常处理]
      异常1: PromExportError - 拉取失败，降级本地 buffer
    [来源标注] [DD-001:MD-MCP M-D02]
    """

    def __init__(self, settings: Settings) -> None:
        """初始化 Registry 并注入默认标签."""
        self.registry: CollectorRegistry = _REGISTRY
        self.default_labels: list[str] = ["service", "env", "version"]

    def counter(self, name: str, labels: Iterable[str]) -> Counter:
        """创建/获取 Counter 实例.

        [关联接口契约] IC-018（metrics.expose）
        [参数说明]
          参数1: name str 必填 指标名（snake_case，prefix: agenthub_）
          参数2: labels Iterable[str] 必填 label 列表（基数必须可控）
        [返回值]
          类型: Counter
          描述: prometheus_client.Counter 实例
        [前置条件] name 符合 [a-zA-Z_:][a-zA-Z0-9_:]*；labels 元素已 str 化
        [后置条件] Counter 已注册到 _REGISTRY
        [并发安全] prom client 内部加锁，线程安全
        [幂等性] 同 (name, tuple(labels)) 返回同一实例
        [性能约束] 单次创建 O(1)
        [来源标注] [DD-001:IC-018 / MD-MCP M-D02 get_counter]
        """
        raise NotImplementedError

    def gauge(self, name: str, labels: Iterable[str]) -> Gauge:
        """创建/获取 Gauge 实例.

        [关联接口契约] IC-018（metrics.expose）
        [参数说明]
          参数1: name str 必填 指标名
          参数2: labels Iterable[str] 必填 label 列表
        [返回值] 类型: Gauge；描述: prometheus_client.Gauge 实例
        [并发安全] 线程安全
        [幂等性] 同 (name, tuple(labels)) 返回同一实例
        [来源标注] [DD-001:IC-018]
        """
        raise NotImplementedError

    def histogram(
        self, name: str, labels: Iterable[str], buckets: Iterable[float] | None = None
    ) -> Histogram:
        """创建/获取 Histogram 实例.

        [关联接口契约] IC-018（metrics.expose）
        [参数说明]
          参数1: name str 必填
          参数2: labels Iterable[str] 必填
          参数3: buckets Iterable[float] 可选 默认 [0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2.5,5,10]
        [返回值] 类型: Histogram
        [来源标注] [DD-001:IC-018]
        """
        raise NotImplementedError

    def render(self) -> bytes:
        """渲染 exposition 文本.

        [职责] 生成 Prometheus 文本格式（UTF-8）.
        [返回值] 类型: bytes；描述: text/plain exposition
        [性能约束] /metrics < 100ms（[DD-001:IC-018]）
        [来源标注] [DD-001:IC-018]
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 模块级便捷函数（与 MD-MCP M-D02 函数签名一致）
# ---------------------------------------------------------------------------

def get_counter(name: str, labels: list[str]) -> Counter:
    """[函数名] get_counter.

    [职责] 工厂函数：获取 Counter（无 MetricsRegistry 显式实例时）.
    [关联接口契约] IC-018
    [参数说明]
      参数1: name str 必填 指标名
      参数2: labels list[str] 必填 label 列表
    [返回值] Counter 实例
    [来源标注] [DD-001:MD-MCP M-D02 函数签名]
    """
    raise NotImplementedError


def get_gauge(name: str, labels: list[str]) -> Gauge:
    """[函数名] get_gauge.

    [职责] 工厂函数：获取 Gauge.
    [关联接口契约] IC-018
    [来源标注] [DD-001:MD-MCP M-D02 推断]
    """
    raise NotImplementedError


def get_histogram(name: str, labels: list[str], buckets: list[float] | None = None) -> Histogram:
    """[函数名] get_histogram.

    [职责] 工厂函数：获取 Histogram.
    [关联接口契约] IC-018
    [来源标注] [DD-001:MD-MCP M-D02 推断]
    """
    raise NotImplementedError
