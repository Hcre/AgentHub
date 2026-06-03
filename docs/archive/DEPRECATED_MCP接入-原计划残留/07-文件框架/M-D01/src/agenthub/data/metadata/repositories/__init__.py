"""Repositories 包入口 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/__init__.py
[文件职责] 聚合 30 Repository 公共导出
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:FS-019 + MD:M-D01 + IC-017]
[功能描述]
  功能1: 重新导出 BaseRepository[T] 泛型基类
  功能2: 重新导出 19 ORM 模型对应的 Repository（按业务域聚合到 5 个文件，1:1 类映射保持）
  功能3: 重新导出 Specification 基类与常用规约
[输入输出]
  输入: 调用方 from agenthub.data.metadata.repositories import MCPServerRepository
  输出: Repository 类
[依赖关系]
  依赖文件: ./base.py, ./market_repos.py, ./pool_repos.py, ./approval_repos.py,
            ./submission_repos.py, ./system_repos.py, ./specifications.py
  被依赖文件: ../unit_of_work.py
[注意事项]
  注意1: Repository 实例必须通过 UnitOfWork 构造，禁止直接 new
  注意2: 按业务域分组以减少文件数（FDR-MD01-002）；类级别仍保持 1:1 ORM 映射
[代码风格] 遵循 [DD-001:CS-MCP §1.5]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:FS-019 + IC-017 + DD-M推断:依据=域聚合文件组织减少文件碎片化（FDR-MD01-002）]
"""

__all__: list[str] = []
