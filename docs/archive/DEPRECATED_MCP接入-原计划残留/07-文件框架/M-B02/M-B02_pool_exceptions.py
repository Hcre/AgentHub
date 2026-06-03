"""M-B02 Process Pool Manager 异常定义.

[文件路径] src/agenthub/application/pool/exceptions.py
[文件职责] 定义 Process Pool 模块领域异常（继承 AgentHubError 基类）
[所属模块] M-B02
[关联设计规范] MD-MCP-V1.0-20260602 / EX-002
[功能描述]
  功能1: 定义 PoolFullError（429 池满）
  功能2: 定义 SpawnFailedError（500 fork 失败）
  功能3: 定义 HealthCheckTimeout（健康检查超时 → zombie 计数）
  功能4: 定义 DistributedLockTimeout（PG + Redis 双层锁超时）
[输入输出]
  输入: 异常构造参数（message / code / http_status）
  输出: 领域异常实例
[依赖关系]
  依赖文件: agenthub.core.exceptions
  被依赖文件: agenthub.application.pool.services, agenthub.application.pool.controllers
[注意事项]
  注意1: 所有异常必须继承 AgentHubError 以保证统一 {code, message, trace_id} 响应
  注意2: PoolFullError 的 http_status=429，调用方需实现重试 1 次逻辑
  注意3: SpawnFailedError 触发 reserved_slot + 报警（EX-002）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.6 异常处理规范
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B02 - 初始版本
[作者] DD-M-B02-20260603
[来源标注] [DD-001:MD-MCP-M-B02 + EX-002]
"""
from agenthub.core.exceptions import BusinessError, SystemError


class PoolFullError(BusinessError):
    """进程池已满异常（HTTP 429）.

    触发条件: workspace 内活跃进程数达到 64 上限
    处理流程: 触发 LRU 驱逐（evict_lru(1)）→ 重试 1 次 → 仍满则上抛
    """

    code: str = "POOL_FULL"
    http_status: int = 429


class SpawnFailedError(SystemError):
    """进程 spawn 失败异常（HTTP 500）.

    触发条件: subprocess fork / posix_spawn 返回非零退出码
    处理流程: reserved_slot 保留 + 告警 ERROR + 重试 max 3
    """

    code: str = "POOL_SPAWN_FAILED"
    http_status: int = 500


class HealthCheckTimeoutError(SystemError):
    """健康检查超时异常.

    触发条件: healthcheck 命令 30s 内未返回
    处理流程: fail_count++（上限 3 → 状态机转 zombie → 回收）
    """

    code: str = "POOL_HEALTH_CHECK_TIMEOUT"
    http_status: int = 500


class DistributedLockTimeoutError(SystemError):
    """分布式锁获取超时异常.

    触发条件: PG row-lock 与 Redis Redlock 均超时
    处理流程: 触发降级链路（PG → Redis）[DD洞察-1]，3 次失败上抛
    """

    code: str = "POOL_LOCK_TIMEOUT"
    http_status: int = 503
