"""
[文件路径] src/agenthub/access/cron/__init__.py
[文件职责] M-A04 Cron Scheduler 模块包初始化与公共接口导出
[所属模块] M-A04（来自DD-001）
[关联设计规范] FS-004 / MD-MCP-V1.0-20260602.md#M-A04
[功能描述]
  功能1: 暴露 CronApp、LeaderElector、JobDispatcher、CronAuditor 公共类
  功能2: 集中管理模块版本与元信息
  功能3: 提供 DaemonSet 启动入口 create_cron_app()
[输入输出]
  输入: 无（包初始化）
  输出: 公共类与工厂函数
[依赖关系]
  依赖文件: app.py / scheduler.py / leader_elector.py / dispatcher.py / auditor.py
  被依赖文件: src/agenthub/main.py（K8s CronDeployment 启动入口）
[注意事项]
  注意1: 仅导出公共 API，私有类以下划线前缀并禁止外部引用
  注意2: 模块版本必须与 pyproject.toml 中 agenthub 版本一致
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1（Python 风格指南）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-04 - 初始框架（仅含注释，无业务代码）
[作者] DD-M-04-20260603
[来源标注] [DD-001:FS-004 / MD-MCP-V1.0-20260602.md#M-A04]
"""
from __future__ import annotations

# [DD-M推断:基于 FS-004 文件结构，公共 API 导出应集中于 __init__.py]
# 公共类将在结构设计师（DD-S）阶段从子模块导入
__all__ = [
    "CronApp",
    "LeaderElector",
    "JobDispatcher",
    "CronAuditor",
    "create_cron_app",
]

__version__ = "1.0.0"
__module_id__ = "M-A04"
