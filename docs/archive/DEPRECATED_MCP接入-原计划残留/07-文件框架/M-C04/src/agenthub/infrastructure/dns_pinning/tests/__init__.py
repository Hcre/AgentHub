"""agenthub.infrastructure.dns_pinning.tests 测试包初始化.

[文件路径] src/agenthub/infrastructure/dns_pinning/tests/__init__.py
[文件职责] DNS Pinning 测试包初始化（pytest 探针）
[所属模块] M-C04（DNS Pinning，来自 DD-001）
[关联设计规范] FS-013 / MD-MCP:M-C04 测试策略 / CS-MCP §1.7 测试规范
[功能描述]
  功能1: 标识 tests 目录为 Python 包，供 pytest 发现
  功能2: 暴露公共 conftest fixtures（[CS-001 §1.7] fixtures 在 conftest.py）
[输入输出] 无
[依赖关系]
  依赖文件: 无
  被依赖文件: ./test_pinner.py, ./test_cache.py, ./test_resolver.py, ./test_blacklist.py, ./test_redirect.py
[注意事项]
  注意1: 不在此处放具体测试用例，遵循 [CS-001 §1.7] fixtures-only-in-conftest 原则
  注意2: 异步测试使用 @pytest.mark.asyncio
[代码风格] 遵循 CS-MCP §1 Python 风格
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C04 - 初始版本
[作者] DD-M-C04-20260603
[来源标注] [DD-001:MD-MCP:M-C04 测试策略]
"""
