# 2026-06-09 #2 Tasks + #3 Inbox 全栈持久化 CRUD 落地

> 作者: 袁 (xiangbianpangde) · 分支: `feature/frontend/preview-tabs` · 状态: 待 commit/push

## 背景

STATUS.md §⚠️「后端已做/前端未做」13 项缺口中，仅剩 **#2 Tasks** 与 **#3 Inbox** 两项未闭环。
此前两者后端均为 **mock 骨架**（`tasks.py`/`inbox.py` 返空 + `note:"M3/M4 实现"`），前端 store 全从 `data/mock` 读。
本轮按 user 选定口径 **「两个都做完整 CRUD 落地」+「Tasks 先做持久化 CRUD（不接真实派发编排）」** 补完。

## 做了什么

### 后端（5 层洋葱，复用既有领域资产）

#### Tasks（复用既有 `tasks` 表 + 领域 `Task` 实体 + `TaskRepository` 接口）

- `domain/entities/task.py`：追加 2 个可选展示层字段 `assignee_label` / `due_label`（默认 None，task_engine 不依赖，向后兼容）
- `infrastructure/repositories/task_repository.py`：新建 `PostgresTaskRepository`（save/get/filter/list_subtasks/delete）
- `application/services/task_service.py`：新建 `TaskService`（create/get/list/update/delete）
- `schemas/task.py`：`TaskCreate`/`TaskUpdate`/`TaskOut`/`TaskListOut`，status/priority field_validator → 非法值 422
- `api/routers/tasks.py`：mock 骨架 → 5 端点 CRUD（GET 列表带 status/priority 筛选、POST、GET/{id}、PATCH/{id}、DELETE/{id}）

#### Inbox（从零建实体）

- `domain/entities/inbox.py` + `domain/repositories/inbox_repository.py`：新建 `InboxItem` 实体（mark_read/resolve 状态流转）+ 抽象接口
- `infrastructure/repositories/inbox_repository.py`：`PostgresInboxRepository`
- `application/services/inbox_service.py`：`InboxService`（create/list/unread_count/mark_read/resolve）
- `schemas/inbox.py` + `api/routers/inbox.py`：5 端点（GET 列表/unread-count、POST 创建、POST /{id}/read、POST /{id}/resolve approve|reject）
- `domain/enums.py`：新增 `InboxItemStatus`（unread/read/resolved）+ `InboxResolution`（approved/rejected）

#### 迁移 + 接线

- `alembic/versions/0020_create_tasks_inbox.py`：tasks 表补 `assignee_label`/`due_label` 两列（幂等 inspector 守卫）+ 新建 `inbox_items` 表
- `models.py`：既有 `TaskModel` 加 2 列；新增 `InboxItemModel`
- `api/deps.py` + 3 个 `__init__.py`：注册 repo/service provider 与导出

### 前端（弃 mock 接真 API）

- `api/tasks.ts`：UI↔领域**词表映射**（status: todo↔pending / doing↔running / blocked↔blocked / done↔completed；priority: normal↔medium）+ list/create/update/remove
- `api/inbox.ts`：list/unreadCount/markRead/resolve(approve|reject) + payload.diff/impact 映射
- `stores/taskStore.ts`：弃 `data/mock`，加 `load()`，moveTask/addTask/createTask/removeTask 改乐观更新 + 后端持久化 + 失败回滚
- `stores/inboxStore.ts`：弃 mock，加 `load()`，resolve 改签名 `(id, action)`
- `components/tasks/TasksTabView.tsx` + `inbox/InboxView.tsx`：mount 调 `load()`；审批按钮传 approve/reject
- `components/layout/NavRail.tsx`：新增「收件箱」入口（section='inbox'），闭 **TD-05** 「inbox UI 无 nav」子缺口

## 验证（三档独立）

- **静态门**: tsc 绿 + eslint 绿（前端改动文件）；ruff 绿（后端新增文件，enums.py 2 处 UP036/UP042 为 HEAD 既存非本轮引入）
- **单测**: `tests/test_tasks_inbox.py` 9 个三路径（正常/异常/边界）全绿；全量 `pytest` **332 passed**（= 改动前基线，0 回归；19 fail/2 error 均为 redis-down 的 `test_reactive_router` flaky + 既存 broken 模块，与本轮无关）
- **live**: alembic upgrade head 至 0020 通过（fresh sqlite）；TestClient 跑通全部 10 端点（含 create/list/patch/delete/404 + resolve/unread-count/422）
- **Playwright 浏览器 E2E**（vite 9500 + backend 8000，per [[verify-ui-in-browser]]）:
  - `tasks-inbox-01-tasks-loaded.png` — 2 个 seed 任务按状态映射正确入列（running→进行中, pending→待处理）
  - `tasks-inbox-02-task-persisted-after-reload.png` — UI 创建任务→**整页刷新后仍在**（证明真持久化非本地态）
  - `tasks-inbox-03-inbox-approval.png` — seed 审批条目 + 批准/驳回按钮
  - `tasks-inbox-04-inbox-approved-empty.png` — 点批准→条目移除「收件箱已清空」，后端 status=resolved/resolution=approved
  - 截图落 `docs/deliverables/screenshots/tasks-inbox-0{1..4}-*.png`（已 `ls` 核实 84–195KB 非 0 字节）

## 暴露并修复的真 bug

- **非法 enum 入参 500 → 422**：路由 `TaskPriority(body.priority)` 对非法值（如前端 UI 词 `normal` 误直传）抛 ValueError → 未捕获 500。修：`schemas/task.py` 加 `field_validator` 校验 status/priority，非法 → 422。（前端始终映射为合法值，但 API 边界须健壮）

## 诚实标注

- Tasks 仅做**持久化 CRUD**，未接 `task_engine` 真实派发编排（派给 Agent 真跑需 LLM key + 完整链路，留 M3+）。
- 看板初始为空（DB 无 seed），符合预期；本轮 E2E 的 seed 数据经 live API 写入。
- 本地 dev.db 已 `alembic upgrade head` 到 0020（sqlite, gitignored, 不提交）。

## 给下一位的交接

- 改动**未 commit 未 push**（per [[no-push-without-ask]]）。建议拆 commit：`feat(backend): Tasks+Inbox 持久化 CRUD + alembic 0020` / `feat(frontend): Tasks+Inbox 接真 API + 收件箱 nav 入口`。
- 后续可做：Tasks 接 Coordinator `POST /api/tasks` 自动建任务（M3 派发）；Inbox 与群聊 requiresApproval 真实写入打通；群聊 GroupMessageItem 删除维度。
- 关联缺口：本轮闭 **TD-05** 的「inbox UI 无 nav」子项（backend TODO / frontend mock 两项已随本轮清）。
