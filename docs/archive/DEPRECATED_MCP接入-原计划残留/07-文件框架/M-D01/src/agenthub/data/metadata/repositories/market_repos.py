"""Market 域 Repository 集合 - M-D01.

[文件路径] src/agenthub/data/metadata/repositories/market_repos.py
[文件职责] 聚合 MCPServer / MCPInstallation / Workspace / UserBinding 4 个 Repository
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:IC-017 + MD:M-D01 + FS-019 + DS-001/002/003/006]
[功能描述]
  功能1: MCPServerRepository - 市场目录 CRUD
  功能2: MCPInstallationRepository - 安装记录 CRUD
  功能3: WorkspaceRepository - 工作区 CRUD
  功能4: UserBindingRepository - 用户绑定 CRUD
[依赖关系]
  依赖文件: ./base.py, ../models/mcp_server.py, ../models/mcp_installation.py,
            ../models/workspace.py, ../models/user_binding.py, ./specifications.py
  被依赖文件: ../unit_of_work.py, M-B01 services, M-B03 services
[注意事项]
  注意1: 域聚合（FDR-MD01-002），4 类保持 1:1 ORM 映射
  注意2: 跨实体查询（如 list_servers_with_install_count）走 services 层组合，禁止在 Repository 内 join 跨域表
[代码风格] 遵循 [DD-001:CS-MCP §1 + IC-017]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:IC-017 + DS-001/002/003/006]
"""

# ============================================================
# [类名] MCPServerRepository
# [职责] mcp_servers 表 CRUD + Spec 查询
# [继承] BaseRepository[MCPServer]
# [方法列表]
#   async get(id: UUID) → MCPServer | None
#   async get_by_name(name: str) → MCPServer | None
#   async list_published(category: str | None = None, tags: list[str] | None = None) → list[MCPServer]
#   async search(q: str, limit: int = 20) → list[MCPServer] - 全文搜索（pg_trgm / tsvector）
#   async add(entity: MCPServer) → UUID
#   async update_status(id: UUID, status: str) → None - 仅允许 draft→published→deprecated
# [关联接口契约] IC-017 + 被 M-B01 services 调用
# [来源标注] [DD-001:DS-001 + MD:M-B01]
# ============================================================

# ============================================================
# [类名] MCPInstallationRepository
# [职责] mcp_installations 表 CRUD
# [继承] BaseRepository[MCPInstallation]
# [方法列表]
#   async get_by_mcp_and_workspace(mcp_id: UUID, workspace_id: UUID) → MCPInstallation | None
#   async list_by_workspace(workspace_id: UUID) → list[MCPInstallation]
#   async mark_uninstalled(id: UUID) → None - status='uninstalled'（软删）
# [来源标注] [DD-001:DS-002]
# ============================================================

# ============================================================
# [类名] WorkspaceRepository
# [职责] workspaces 表 CRUD
# [继承] BaseRepository[Workspace]
# [方法列表]
#   async get_by_name(name: str) → Workspace | None
#   async list_by_admin(admin_id: UUID) → list[Workspace] - 查找用户所管理的工作区
# [来源标注] [DD-001:DS-003]
# ============================================================

# ============================================================
# [类名] UserBindingRepository
# [职责] user_bindings 表 CRUD
# [继承] BaseRepository[UserBinding]
# [方法列表]
#   async get_by_triplet(user_id: UUID, mcp_id: UUID, workspace_id: UUID) → UserBinding | None
#   async list_by_user(user_id: UUID) → list[UserBinding]
#   async upsert_mapping(user_id, mcp_id, workspace_id, mapping: dict) → UUID - 业务幂等
# [来源标注] [DD-001:DS-006 + MD:M-B03]
# ============================================================
