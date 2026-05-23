# 当前状态

> 最后更新: 2026-05-23
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | 文档治理体系建立 + check_docs.py pre-push hook | 无 | ClaudeAdapter 完整重写 ✅ + 文档治理 ✅ |
| 董 | 域2: CLI 多模型代理实现（cc-haha 分析 + 代理方案设计 + 代码实现） | 待端到端验证（需要真实 API Key） | ADR-01 ✅ + v4 PRD ✅ + adapter-cli-flow-analysis v1.3 ✅ + CLI 多模型代理方案设计 ✅ + proxy handler/router 实现 ✅ + ClaudeCodeRuntime 适配代理模式 ✅ |

## Git ↔ 目录映射

> check_worklog.py 用它来判断「你是谁」，从而检查对应目录的日志。

| Git用户名 | 日志目录 |
|-----------|----------|
| oldmanpushbike | 黎 |
| （待补充） | 董 |
| （待补充） | 袁 |
=======
| 黎 | 域2: ClaudeCliAdapter(M2) + Agent settings 扩展 | 无 | ClaudeAdapter 完整重写(5种事件+memory注入+重试) ✅ + spec v0.2 对齐 ✅ + DOC-15 v1.1 裁决 ✅ |
| 董 | 域2: adapter-cli-flow-analysis v1.3 + session/permission 方案落地 | 无 | ADR-01(API→CLI 重心转移) ✅ + v4 PRD 统一方案 ✅ + adapter-cli-flow-analysis v1.3 ✅ + doc-sync(spec 同步/架构文档更新) ✅ |
<<<<<<< HEAD
<<<<<<< HEAD
| 袁 | 前端 Phase 0: 重建 Vite + React + TS 工程基座 | 无 | 部署 v0 原型 ✅ + Phase 0 重建(Vite8/React19/TS6/Tailwind4/Zustand)✅ 原型移入 prototype/ ✅ 多阶段 Docker 部署 ✅ 验收 Gate 全绿(tsc/build/eslint/prettier/容器 5173)✅ |
>>>>>>> b0e8bdb (feat(frontend): Phase 0 — 重建 Vite + React + TS 工程基座)
=======
| 袁 | 前端 Phase 1 完成，下一步 Phase 2 聊天 UI | 无 | Phase 0 工程基座 ✅ + Phase 1 三栏布局(AppShell/Left/Center/Right)+ ui 设计系统(11 组件)+ 类型统一 + uiStore ✅ 验收全绿 + 截图确认渲染 ✅ |
>>>>>>> 7b21a44 (feat(frontend): Phase 1 — 三栏布局 + 设计系统基座)
=======
| 袁 | 前端 Phase 2 完成，下一步 Phase 3 任务看板 | 无 | Phase 0 基座 + Phase 1 三栏布局 + Phase 2 聊天 UI(chatStore/会话切换/气泡/打字/Composer/右栏绑定)✅ 验收全绿 + 截图确认 ✅ |
>>>>>>> b751d77 (feat(frontend): Phase 2 — 聊天 UI 升级)

## 图例
- ⚠️ 阻塞中（写明等谁/等什么）
- 🔀 涉及跨域接口，需协调
- ✅ 完成
