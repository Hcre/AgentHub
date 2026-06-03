"""M-D03 Cache & Queue 测试包入口.

[文件路径] src/agenthub/data/cache/tests/__init__.py
[文件职责] 测试包初始化，导出共享 fixture
[所属模块] M-D03（来自 DD-001）
[关联设计规范] FS-021 / MD-M-D03（来自 DD-001）
[功能描述]
  功能1: 集中 fixture 入口
  功能2: 共享 fakeredis-cluster 实例
[输入输出]
  输入: 无
  输出: 共享测试夹具
[依赖关系]
  依赖文件: pytest、fakeredis
  被依赖文件: test_client.py、test_proxy.py、test_stream.py、test_pubsub.py
[注意事项]
  注意1: fakeredis 必须支持 cluster 模式（fakeredis>=2.20）
  注意2: 集成测试需真 Redis cluster（testcontainers）
[代码风格] 遵循 CS-MCP-V1.0 §1.7（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-D03 - 初始测试包
[作者] DD-M-D03-20260602
[来源标注] [DD-001:FS-021 / MD-M-D03:测试策略]
"""
