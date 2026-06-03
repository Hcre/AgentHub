"""Tests 包入口 - M-D01.

[文件路径] src/agenthub/data/metadata/tests/__init__.py
[文件职责] M-D01 单元/集成测试包标记
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:CS-MCP §1.7 测试规范 + MD:M-D01 测试策略]
[功能描述] 标记 tests/ 为 Python 包；fixture 集中在 conftest.py
[依赖关系] 子文件 test_base_repository.py / test_unit_of_work.py / test_specifications.py / test_models_appendonly.py / test_approval_repos.py / test_pool_repos.py
[注意事项]
  注意1: 测试覆盖率目标行 ≥ 90%（核心 Repository）
  注意2: 使用 pytest-asyncio + testcontainers 真 PG（[MD:M-D01 测试策略]）
[代码风格] 遵循 [DD-001:CS-MCP §1.7]
[创建日期] 2026-06-03
[作者] DD-M-D01-20260603
[来源标注] [DD-001:CS-MCP §1.7 + MD:M-D01]
"""
