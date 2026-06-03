"""M-B01 测试包初始化.

[文件路径] src/agenthub/application/market/tests/__init__.py
[文件职责] pytest 探测包；集中 conftest fixture 引用
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01
[功能描述]
  功能1: 让 pytest 识别 tests 为 package
  功能2: 不在此处放 fixture（[CS-001 §1.7] fixture 集中 conftest.py）
[输入输出] 无
[依赖关系] 无
[注意事项] 注意1: 不依赖业务代码（避免循环）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-02
[作者] DD-M-B01-20260602
[来源标注] [DD-001:CS-MCP#§1.7]
"""
