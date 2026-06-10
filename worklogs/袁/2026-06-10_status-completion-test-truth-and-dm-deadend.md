# 2026-06-10 STATUS 收尾：绿测真相恢复 + 私聊死路闭环

- **谁**: 袁 (xiangbianpangde)
- **分支**: main（per [[merge-to-main-approved]] 常驻权限；2 commit 本地 ahead，**未 push** per [[no-push-without-ask]]）
- **目标**: `/goal 完成 STATUS.md 所有内容，除了录制视频`

## 背景
接手即跑 baseline，发现 STATUS 多处"全绿/已闭环"声明与实测矛盾——典型 [[feedback-no-fake-evidence]] 失信模式。优先把声明对齐真相，再推进真实功能缺口。

## 做了什么

### 1. 绿测真相恢复 (TD-17, commit `2135d3b`)
baseline 实测 **12 后端 + 4 前端用例 fail**（STATUS/TD-14 标"356 全绿"、pin worklog 标"9/9"）。逐个定位，全部是断言**已被 v4 故意删除行为**的陈旧测试：

| 失败测试 | 根因（已发布行为） | 处理 |
|---|---|---|
| `test_pin_session_ownership` owner 403 / anonymous 401 | commit `11b4c6c` **移除** pin JWT+owner 校验（前端无登录流程，强制 JWT 让功能不可用）；commit 标题"端点鉴权"与实码相反 | rewrite 断言放宽后契约：非 owner 可 pin、匿名路由无鉴权门槛（fake service 覆盖 dep） |
| `test_reflex_control_hits/misses` (9) | v4 R5 删 `ChatService._is_control` 机械停词反射，"停/取消"改由 `reactive_router` LLM 分类（含"停一下"应 relay 的细微判断） | 删除陈旧用例 + 注释说明迁移 |
| `test_pi_agent_e2e::test_subprocess_lifecycle` | `PiAgentRuntime.__init__` 不再收 model/provider/api_key/base_url | 改用当前签名 + 加 `shutil.which('pi')` skip guard |
| `MessageBubble.pin` / `GroupMessageItem.pin` rollback | `11b4c6c` 删 inline error 元素，只 console.error | 断言无 error 元素 + console.error 被调 |
| `WebPreviewCard.fullscreen` (2) | 全屏 Dialog 改为侧栏 preview tab (`useUIStore.addPreviewTab`) | rewrite 断言新侧栏行为 + 删死 `Maximize2` import |

**实测结果**: 后端 346 passed / 3 skipped、前端 116 passed、tsc + eslint 绿。

### 2. 私聊 1v1 死路修复 (TD-06/07, commit `e0a8494`)
**真 bug**: 后端已存在的 private session 从不回灌前端 store → 刷新即丢、无法续聊；空态无可点入口。
**改动**:
- `chatStore.hydrateFromSessions(sessions)`: private SessionOut → Conversation，用 `session.id` 当本地 conv id（幂等）+ 写 `sessionIds[convKey]=session.id`（ChatView 续聊真实 session）；保留本地 archived。
- `LeftPanel` mount effect 调 `sessionsApi.list({type:'private'})` → hydrate；后端挂静默降级。
- 空态「发起私聊」CTA → `setSection('agent-detail')`（AgentsListPage）。

**验证 (Playwright live, :5300 + 后端 :8000)**:
- 私聊列表回灌 37 条后端 session（subtitle「历史会话」），**37/37 均带后端 sessionId**（`sessionIds[convKey]===conv.id`，全部可续聊）。
- 0 console error / 0 warning；截图 `docs/deliverables/screenshots/p0-private-hydration-2026-06-10.png`。
- 5 vitest（`chatStore.hydrate.test.ts`：回灌/幂等/保留 archived/跳过群聊/默认名）。

**诚实标注**: 空态 CTA 已落码 + tsc/eslint 绿 + store action 单测，但 seeded DB 总返回 session，空态在 live 不可复现，故 CTA 仅 code+unit 级验证、未截 live 空态图。

## 环境备注
- DB 在 Docker 主机端口 **15432**（非文档写的 5432）；alembic stamp 漂移（DB=0024 / 本地 head=0023，多 worktree 残留）已 realign 到 0023。
- 后端 :8000、前端 vite :5300。

## 给下一位的交接
- **未 push** 共 3 commit（`2135d3b` + `e0a8494` + STATUS/worklog commit）。等用户说推。
- **STATUS 剩余真缺口**（按 `docs/plan/06-09-袁-status完成/` 估时，均非本会话可一次做完）：
  - 代码冲突处理 ❌ (16-22h, 需 workspace git repo)
  - 任务派发 FSM/DAG M3+ (12-16h, 需 PR-01)
  - PPT 浏览 ❌ / 版本历史 ❌ / 对话式局部修改 ❌ (P2, 各 ~6-9h)
  - 对话式创建 Agent ⚠️ (10-14h, 需 LLM key + PR-01)
  - 部署真实流水线 ⚠️ (1.5-2 周)
  - 桌面端 Tauri 📋 (5-7 周, 阻塞于董/黎 PR-01 二审)
- **根治建议**: CI 去 `continue-on-error`，让红测真拦 PR——否则绿测漂移会反复复发（TD-14→TD-17 已两次）。
