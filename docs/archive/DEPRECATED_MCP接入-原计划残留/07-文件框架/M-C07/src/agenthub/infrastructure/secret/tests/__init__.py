"""M-C07 Secret Manager 测试包.

[文件路径] src/agenthub/infrastructure/secret/tests/__init__.py
[文件职责] 测试包初始化（共享 fixture 入口）
[所属模块] M-C07
[关联设计规范] FS-016 / MD-M-C07 / CS-MCP-V1.0 §1.7
[功能描述]
  功能1: 暴露共享 fixture 入口（Vault mock / fakeredis / 异步 client）
  功能2: 标记 pytest 收集根
[输入输出] n/a
[依赖关系]
  依赖文件: conftest.py（建议由 Dev 创建于本目录或 tests/unit/）
  被依赖文件: test_vault_client.py / test_token_manager.py / test_transit.py / test_cache.py
[注意事项]
  注意1: 测试用例会 Mock Vault SDK；不得发起真实网络请求
  注意2: pytest-asyncio 模式 auto（CS §1.7）
  注意3: 测试不打印 secret 明文；fixture 提供固定 fake secret
[代码风格] 遵循 CS-MCP-V1.0 §1.7
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C07 - 初始框架
[作者] DD-M-C07-20260603
[来源标注] [DD-001:FS-016/MD-M-C07 + CS-MCP-V1.0 §1.7]
"""

# 共享 fixture 由 conftest.py 提供；本文件留空
