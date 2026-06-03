"""MCPServer ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/mcp_server.py
[文件职责] 映射 PG 表 mcp_servers（市场目录）的 SQLAlchemy ORM 模型
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-001 + DE-001 + FS-019]
[功能描述]
  功能1: 定义 MCPServer 类，映射 19 张 PG 表中的 mcp_servers
  功能2: 暴露 id / name / version / category / tags / manifest_json / owner_id / status / created_at / updated_at 字段
  功能3: 声明唯一索引 (name) + GIN 索引 (tags) + 外键 owner_id → users(id) + CHECK status IN draft/published/deprecated
[输入输出]
  输入: SQLAlchemy session.add(MCPServer(...)) / session.get(MCPServer, id)
  输出: MCPServer 实例供 Repository 层 CRUD
[依赖关系]
  依赖文件: ./base.py (Base, UUIDPrimaryKeyMixin, TimestampMixin)
  被依赖文件: ../repositories/mcp_server.py, ../repositories/specifications.py
[注意事项]
  注意1: manifest_json 列使用 JSONB（非 JSON），便于 PG 端 GIN 索引和路径查询
  注意2: tags 为 TEXT[]，GIN 索引必须显式声明 postgresql_using="gin"
  注意3: status 字符串而非 Enum（Alembic 迁移 Enum 列变更代价高，采用 VARCHAR(16) + CHECK 约束）
[代码风格] 遵循 [DD-001:CS-MCP §1.3 类型注解 + §2 SQL 规范]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-001 + DE-001 + FS-019]
"""

# ============================================================
# [类名] MCPServer
# [职责] 映射 mcp_servers 表，承载市场目录核心数据
# [关联设计规范] [DD-001:DS-001 + MD:M-D01]
# [属性]
#   id: Mapped[UUID] - 主键 (gen_random_uuid())
#   name: Mapped[str] - VARCHAR(128) UNIQUE NOT NULL
#   description: Mapped[str | None] - TEXT NULL
#   version: Mapped[str] - VARCHAR(32) NOT NULL (semver)
#   category: Mapped[str] - VARCHAR(64) NOT NULL INDEX
#   tags: Mapped[list[str]] - TEXT[] NOT NULL GIN
#   manifest_json: Mapped[dict[str, object]] - JSONB NOT NULL
#   owner_id: Mapped[UUID] - FK→users(id) INDEX
#   status: Mapped[str] - VARCHAR(16) NOT NULL default 'draft' CHECK IN (draft/published/deprecated)
#   created_at / updated_at: Mapped[datetime] - TimestampMixin
# [方法列表] 仅 ORM；业务方法由 Repository 提供
# [状态机] status: draft → published → deprecated（单向，DDR 待定迁移路径）
# [异常处理]
#   IntegrityError: name 重复 / owner_id 外键缺失 / status 越界（CHECK 触发）
# [来源标注] [DD-001:DS-001]
# ============================================================
