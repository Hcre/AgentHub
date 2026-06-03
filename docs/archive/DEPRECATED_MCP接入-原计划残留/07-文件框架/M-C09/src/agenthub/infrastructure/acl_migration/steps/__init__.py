"""
[文件路径] src/agenthub/infrastructure/acl_migration/steps/__init__.py
[文件职责] M-C09 Step 抽象基类与 4 步具体类导出
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09（来自 DD-001）
[功能描述]
  功能1: 导出 MigrationStep 抽象基类
  功能2: 导出 4 步具体类（Snapshot/Apply/Verify/Commit）
  功能3: 提供 Step 工厂（按 name 构造）
[输入输出]
  输入: 无（包初始化）
  输出: 公共符号
[依赖关系]
  依赖文件: .snapshot, .apply, .verify, .commit
  被依赖文件: .orchestrator, .compensator
[注意事项]
  注意1: MigrationStep 必须定义 forward(ctx) 与 compensate(ctx) 两个抽象方法
  注意2: 4 步必须按 Snapshot→Apply→Verify→Commit 顺序执行（编排器强校验）
[代码风格] 遵循 CS-MCP Python
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-001:FS-018/MD-MCP-M-C09]
"""
from .base import MigrationStep
from .snapshot import SnapshotStep
from .apply import ApplyStep
from .verify import VerifyStep
from .commit import CommitStep

__all__ = [
    "MigrationStep",
    "SnapshotStep",
    "ApplyStep",
    "VerifyStep",
    "CommitStep",
]
