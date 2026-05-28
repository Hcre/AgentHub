# 工作日志：Phase 6 — Agent 创建与编辑

- **谁**: 袁
- **日期**: 2026-05-23
- **分支**: xbpd
- **关联 Spec**: `docs/前端实施计划_v1.md` §6

## 目标
让 Agent 可创建/编辑/删除：把静态 agents 提升为可变 store，加创建表单与详情设置编辑。

## 产出
- [x] Provider 类型 + `data/extra.ts` providers（anthropic/openai/azure + models）
- [x] `src/stores/agentStore.ts`：agents + profiles（seed mock+extra）+ createAgent/removeAgent/updateConfig
- [x] §6.1 `components/agent/CreateAgentModal.tsx`：name/role(必填) + provider/model 联动下拉 + api_key(password) + 技能(逗号分隔) + system_prompt；提交建 agent 并跳转其会话
- [x] §6.2 `AgentDetailPage` 设置 Tab 改可编辑（maxTokens/并发/temperature 即时写 store）+ 危险区删除（二次确认 → removeAgent → 返回聊天）
- [x] 迁移到 agentStore：LeftPanel（AI 队友列表 + 「+」创建入口 + 会话取 chatStore）、CenterPanel（活动 agent）、AgentDetailPage、SettingsView
- [x] LeftPanel SectionHeader 支持 onAdd「+」
- [x] 验收全绿：tsc 0 / eslint 0（修了 no-unused-vars：removeAgent 改 delete 副本）/ prettier / build；dev 截图确认创建表单渲染

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| agents 提升为 agentStore（agents+profiles） | 创建/删除需可变状态 | LeftPanel/CenterPanel/AgentDetail/SettingsView 改读 store |
| api_key 不入前端 store | 红线：密钥不留存明文 | createAgent 只透传，store 不存；展示用掩码 |
| 删除用组件内二次确认而非全局 confirm | 无全局确认系统，避免 window.confirm | 危险区「删除→确认删除/取消」 |
| 新 agent 无会话时点开用 'c1' 空会话 | mock 无预置会话 | ChatView 空列表 + Composer 可发首条 |
| tasks/group 的成员查找仍用 mock.agents | 新 agent 不会自动进任务/群组（mock） | 已记入待优化，真实数据时统一走 store |

## 未完成 / 阻塞
- [ ] 对话式创建（自然语言生成 system_prompt + 能力）未做，仅表单式（§6.1 备选）。
- [ ] 新建 agent 不出现在任务负责人下拉 / 群组成员（仍读 mock.agents）。
- [ ] provider/model 在详情设置里只读（创建时可选，编辑暂不可改）。
- [ ] 名称唯一性校验未做。

## 给下一位的交接
> Agent CRUD 全在 `agentStore`（agents + profiles）。创建入口：左栏「AI 队友」标题悬停「+」。删除：助手详情→设置→危险区。
> 进 Phase 7（mock → 真实 API + 视觉打磨）：
> - 各 store 初始化从 data/ 换 API：agentStore→GET/POST/PATCH/DELETE /api/agents；chatStore→WS /ws/sessions；taskStore→/api/tasks；groupStore→见 group/HANDOFF；inboxStore→/api/inbox。
> - createAgent/updateConfig/removeAgent 现在是纯前端，接 API 时在这三个 action 内发请求即可（签名稳定）。
> - 视觉打磨：accent 多色 + Tweaks 面板（参考 prototype/src/tweaks-panel.jsx）、字体、动画。
