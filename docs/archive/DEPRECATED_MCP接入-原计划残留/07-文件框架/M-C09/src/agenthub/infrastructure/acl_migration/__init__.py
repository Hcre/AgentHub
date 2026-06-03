"""
[文件路径] src/agenthub/infrastructure/acl_migration/__init__.py
[文件职责] M-C09 ACL Migration 包初始化与公共符号导出
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09（来自 DD-001）
[功能描述]
  功能1: 导出 Saga 编排器 MigrationOrchestrator
  功能2: 导出 Step 抽象基类与具体步骤类
  功能3: 导出状态枚举与结果数据类
  功能4: 导出 Compensator 补偿器
[输入输出]
  输入: 无（包初始化）
  输出: 公共符号（类/枚举/数据类）
[依赖关系]
  依赖文件: .orchestrator, .compensator, .steps
  被依赖文件: 任何调用 acl_migration 的上层（如 M-C05 调用方、运维脚本）
[注意事项]
  注意1: 严禁在此文件实现业务逻辑，仅做 re-export
  注意2: 包对外稳定 API；任何破坏性变更需走 DDR
  注意3: 仅导出与上游 IC-016（acl.migrate）相关的公共符号
[代码风格] 遵循 CS-MCP Python（4空格 / Google Docstring / snake_case / 类型注解）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-001:FS-018/MD-MCP-M-C09]
"""
from .orchestrator import (
    MigrationOrchestrator,
    MigrationResult,
    MigrationState,
    schedule_migration,
)
from .compensator import Compensator, CompensationPlan
from .steps import (
    ApplyStep,
    CommitStep,
    MigrationStep,
    SnapshotStep,
    VerifyStep,
)

__all__ = [
    "MigrationOrchestrator",
    "MigrationResult",
    "MigrationState",
    "schedule_migration",
    "Compensator",
    "CompensationPlan",
    "MigrationStep",
    "SnapshotStep",
    "ApplyStep",
    "VerifyStep",
    "CommitStep",
]
