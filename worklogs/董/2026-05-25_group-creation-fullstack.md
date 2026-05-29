# 群组创建功能 — 全栈实现

> 日期: 2026-05-24 ~ 2026-05-25 | 分支: feature/group/creation | worktree: .worktree/group-creation

## 完成内容

### 前端(7 文件)
- `types/index.ts` — ApiGroup/ApiGroupMember/ApiGroupCoordinator DTO
- `api/groups.ts` — groupsApi.create/list/checkName/rename/remove
- `hooks/useDebounce.ts` — 防抖 hook
- `stores/groupStore.ts` — fetchGroups/createGroup/renameGroup/deleteGroup(API-first+降级)
- `components/group/CreateGroupModal.tsx` — 创建弹窗(双栏成员选择+实时校验)
- `components/layout/LeftPanel.tsx` — 数据源切 groupStore +「群组」+「+」入口 + 右键菜单
- `App.tsx` — 启动 fetchGroups

### 后端(8 文件)
- `models.py` — GroupModel/GroupMemberModel
- `0003_create_groups.py` — 幂等 migration
- `domain/entities/group.py` — Group 聚合根
- `domain/repositories/group_repository.py` — GroupRepository ABC
- `infra/repositories/group_repository.py` — Postgres 实现
- `application/services/group_service.py` — 自动建协调者+CRUD
- `schemas/group.py` — 名称正则(支持中文)+成员上限
- `routers/groups.py` — POST/GET/GET check-name/PATCH/{id}/DELETE/{id}

### 脚本(2)
- `scripts/start-backend.sh` / `scripts/start-frontend.sh`

### UI 交互
- 右键群组 → 重命名(pencil 图标) / 删除群组(trash2 图标,红色,悬停加深)

## 验证

| 项 | 结果 |
|----|------|
| tsc build | ✅ |
| eslint | ✅ |
| ruff 真实问题 | ✅ 0 |
| POST 201 / GET list / check-name | ✅ |
| PATCH 重命名 / DELETE 删除 | ✅ |
| 409 重名 / 422 非法名 | ✅ |
| DB 落库验证 | ✅ |

## 给下一位的交接

- 启动: `cd .worktree/group-creation && bash scripts/start-backend.sh` + `bash scripts/start-frontend.sh`
- 浏览器: http://localhost:4180/
- 群聊消息仍是 mock(设计 §六 划出范围)
- 成员增删/群组编辑删除 API 已就绪,前端未接
- CORS 已配 :5173 + :4180
- 名称正则前后端一致: `^[一-鿿a-zA-Z][一-鿿a-zA-Z0-9_-]{1,31}$`
