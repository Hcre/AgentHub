# 工作日志：Template 系统 v4 重构 --- 常用模板 + UI 重布局 + 默认精选

- **谁**: 黎
- **日期**: 2026-06-08
- **分支**: feature/frontend/template-v4-restructure
- **关联 Spec**: `docs/specs/04-commands_命令接口.md` § 模板端点 / `docs/specs/03-data-model_数据模型.md` § templates 表

## 目标

Template 系统 v4 重构：将模板管理从 Skill 市场独立出来，建立"常用模板"快捷入口，自动注入 skill-creator，并预置 8 个 wshobson/agents 精选常用模板。

## 产出

### 后端

- **DB 层**（`TemplateModel`）：`is_favorite` / `favorite_name` / `favorite_description` / `favorite_order` 四字段（`app/infrastructure/db/models.py:435-438`）
- **领域实体**（`Template`）：同步新增 favorite 四字段 + `update()` 白名单（`app/domain/entities/template.py:38-41,72-75`）
- **仓储接口 + 实现**（`TemplateRepository`）：`set_favorite(template_id, data)` + `list_favorites()` 新增方法（`app/domain/repositories/template_repository.py:52-57` / `app/infrastructure/repositories/template_repository.py:206-232`）
- **Schemas**：`TemplateOut` / `TemplateUpdate` / `SetFavoriteRequest` 含 favorite 字段（`app/schemas/template.py`）
- **API 端点**：`PATCH /templates/{id}/favorite` + `GET /templates/favorites`（`app/api/routers/templates.py:56-61,121-129`）
- **Service 层**（`TemplateService`）：
  - `set_favorite()` / `list_favorites()` 业务方法
  - `_ensure_local_templates()` 重写：9 个本地模板从单文件改为按 slug 子目录写入 `SKILL.md`，解析 YAML frontmatter 入库
  - `_ensure_skill_creator_skill()` 新增：自动注入 skill-creator runtime skill 到 `.agenthub/skills/skill-creator/SKILL.md`
  - **`_ensure_default_favorites()` 新增**：懒初始化，首次访问 `GET /templates/favorites` 时触发 GitHub sync（`wshobson/agents`）→ 按 source_path 精确匹配 8 个精选模板 → 批量标记为常用（`is_favorite=true` + 中文名/简介 + order 1-8）。幂等，已有常用数据则跳过。
  - 8 个默认常用定义（`_DEFAULT_FAVORITES` 类变量）：

  | # | source_path | favorite_name | 职责 |
  |---|-------------|---------------|------|
  | 1 | `plugins/python-development/agents/python-pro.md` | Python 开发专家 | Python 3.12+ 全栈开发 |
  | 2 | `plugins/frontend-mobile-development/agents/frontend-developer.md` | 前端开发专家 | React/TypeScript 前端 |
  | 3 | `plugins/cicd-automation/agents/deployment-engineer.md` | DevOps 工程师 | CI/CD + 容器化部署 |
  | 4 | `plugins/security-compliance/agents/security-auditor.md` | 安全审计专家 | 安全审查与合规 |
  | 5 | `plugins/database-design/agents/database-architect.md` | 数据库架构师 | SQL/NoSQL 建模 |
  | 6 | `plugins/api-scaffolding/agents/backend-architect.md` | API 设计师 | RESTful/GraphQL API |
  | 7 | `plugins/unit-testing/agents/test-automator.md` | 测试工程师 | 测试编写与覆盖率 |
  | 8 | `plugins/documentation-generation/agents/docs-architect.md` | 文档工程师 | 技术文档编写 |

### 前端

- **AgentsListPage** 重布局：双 Tab（"AI 队友" + "模板管理"），各 Tab 独立数据加载（`app/frontend/src/components/agents/AgentsListPage.tsx`）
- **TemplateManagementTab** 重写：卡片网格布局，每卡片含操作按钮行（查看/创建Agent/添加到常用），移除右侧预览面板（`app/frontend/src/components/templates/TemplateManagementTab.tsx`）
- **TemplateCard** 增强：`showActions` prop，hover 显示操作按钮；常用标记星标图标
- **SkillMarketplacePage** 清理：移除创建 skill 按钮和模板 Tab（归入模板管理 Tab）
- **CreateAgentModal** Step 1 新增"常用模板"快捷选区：横向滚动卡片，一键选中常用模板自动填充表单
- **Composer** 新增 skill 创建入口：sparkle 图标按钮，打开 skill-creator 对话
- **templateStore** 扩展：`favorites` 状态 + `fetchFavorites()` + `setFavorite()` actions（`app/frontend/src/stores/templateStore.ts`）

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 模板管理与 Skill 市场分离为独立 Tab | Skill 市场侧重技能发现/安装，模板管理侧重 Agent 创建流程；混在一起用户困惑 | 两页面解耦，各自维护数据加载逻辑 |
| 常用模板预置 8 个（wshobson/agents 精选） | 零配置体验：用户首次打开即有覆盖 Python/前端/DevOps/安全/DB/API/测试/文档 8 大方向的常用模板 | 首次访问 `GET /favorites` 触发 git clone（~30s），后续访问瞬时 |
| source_path 精确匹配而非名称模糊匹配 | wshobson/agents 仓库中同一 agent 名可能出现在多个插件子目录（如 `security-auditor` 同时存在于 `security-compliance` / `security-scanning` / `backend-development`），用路径精确定位避免歧义 | 需实际 clone 仓库确认路径，若上游仓库重命名则需同步更新 |
| 默认常用定义放在 Service 类变量而非数据库 seed | seed 脚本需要 DB session 启动时即存在；Service 类变量在运行时懒加载更灵活 | 非持久化到源代码层面的配置；修改常用列表只需改 Python 代码 |
| 常用模板来源为 GitHub sync 而非本地 my-templates | wshobson/agents 社区维护的专业模板质量高于自建，避免重复造轮子 | 依赖 git + 网络，离线环境退化为空常用列表 |

## 架构变化

```
TemplateService
├── _ensure_local_templates()     ← 9 个本地模板 (my-templates/) 懒入库
├── _ensure_skill_creator_skill() ← skill-creator runtime skill 懒注入
├── _ensure_default_favorites()   ← [NEW] wshobson/agents sync + 8 常用精选
├── sync_source()                 ← GitHub clone/pull + bulk_upsert
├── set_favorite()                ← [NEW] 单模板标为/取消常用
├── list_favorites()              ← [NEW] 列出所有常用，内部调 _ensure
└── list_templates()              ← 调 _ensure_local + _ensure_skill_creator
```

调用链：`GET /api/templates/favorites` → `TemplateService.list_favorites()` → `_ensure_default_favorites()` → `sync_source()` (首次) → `_repo.list(source="wshobson-agents")` → 按路径匹配 8 个 → `_repo.set_favorite()` × 8

## 未完成 / 阻塞

- [ ] 8 个常用模板的 source_path 依赖上游 wshobson/agents 仓库结构不变；若上游重命名文件需手动同步 `_DEFAULT_FAVORITES` 列表
- [ ] 首次 sync_source 克隆仓库 ~30s 需网络 + git，考虑在 docker-compose 启动后 pre-warm

## 给下一位的交接

> 常用模板系统已完整落地。后续如需调整精选列表，修改 `TemplateService._DEFAULT_FAVORITES` 类变量即可（`src/backend/app/application/services/template_service.py:286-327`）。
> 8 个模板的 source_path 均已在 `wshobson/agents` 仓库中验证存在（`.agenthub/templates/sources/wshobson-agents/` 下有实际文件）。
> 前端常用模板 UI 在 `CreateAgentModal` Step 1 和 `TemplateManagementTab` 卡片操作中均可用。
