"""MCPInstallation ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/mcp_installation.py
[文件职责] 映射 PG 表 mcp_installations（MCP 在 workspace 的安装记录）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-002 + DE-002 + FS-019]
[功能描述]
  功能1: 定义 MCPInstallation 类，记录 (mcp_id, workspace_id) 安装关系
  功能2: 字段 id / mcp_id / workspace_id / installer_id / installed_at / status
  功能3: 唯一索引 (mcp_id, workspace_id) 防止重复安装
[输入输出]
  输入: M-B01 Market Service install / uninstall 操作
  输出: 安装记录持久化
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/mcp_installation.py
[注意事项]
  注意1: status 仅 'active' / 'uninstalled'，软删用 status 变更而非 DELETE
  注意2: 卸载时不删行，便于审计追溯（[DD-M推断:依据=append-pattern 用户行为审计]）
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-002 + DE-002]
"""

# ============================================================
# [类名] MCPInstallation
# [职责] 映射 mcp_installations 表
# [属性]
#   id / mcp_id / workspace_id / installer_id / installed_at / status
# [唯一索引] (mcp_id, workspace_id)
# [外键] mcp_id → mcp_servers(id)
# [异常处理] IntegrityError on duplicate installation
# [来源标注] [DD-001:DS-002]
# ============================================================
