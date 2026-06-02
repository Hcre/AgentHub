# 当前状态

> 最后更新: 2026-06-02
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | CLI 自动扫描 + Provider 矩阵 + Step 2 重设计 + OpenCode 集成 (9 bugs 修) | 无 | merge 39 commits ✅ + CLI PATH 扫描 ✅ + ProviderKeyResolver ✅ + Step 2 重设计 ✅ + OpenCode v1.15 集成 ✅ + PiAgentRuntime 修正 ✅ + Key 管理简化 ✅ + 工作目录 E2E ✅ + bug 修复 9 个 ✅ + OpenCode 对话待验证 |
| 董 | 协调者+任务编排部分 | 无 | 群聊全栈实现 ✅ + CLI 多模型代理 ✅ + ADR-02 长驻 CLI ✅ + 前端群聊 ✅ + 记忆系统 B 方向设计 ✅ + B1 后端实现 ✅ + B2 详细设计 ✅ + Agent 创建全链路 6 处 bug 修复 + 9 个测试 ✅ + MCP save_memory 端到端打通 ✅ + 前端记忆面板 ✅ + 记忆分支合并 main ✅ |
| 袁 | MVP 收尾冲刺规划：roadmap+status 同步 + 后续升级计划 v1.0 | 无 | 全项目按模板重构 ✅ + 2026-05-29 目录二次整合（src//docs/ + ~50 文件引用）✅ + skills 移回根 ✅ + 双图谱启用（gen_codegraph.py + CODE_MAP + AI/人视图，0 跨层违规）✅ + 图谱可视化离线化（去 d3 CDN→自包含分层 SVG，上下游高亮）✅ + enums 影响分析（42/58 模块波及，8/10 测试）✅ + dashboard 适配按人协作表 ✅ + src/frontend 代码内容分离（6 文档外迁 docs/）✅ + 全栈运行验证（docker compose 5 服务全 healthy，端点 200）+ celery 健康检查修复 ✅ + 文档命名收敛(AI→CLAUDE/人→README)+docs整合分类+根README/CLAUDE加使用手册 ✅ + dashboard 集成人向文档实时渲染(内置 markdown+TOC) ✅ + dashboard 内嵌代码图谱 Tab ✅ + CODE_MAP.md 收归 docs/ ✅ + 远程 main 同步 5e34bea（12 commits, docs/conventions 恢复）✅ + 后续升级计划 v1.0（8 节 MVP/未实现清单）✅ + roadmap §八 MVP 收尾冲刺（P0-1~6 / P1-1~4 / Demo 脚本 / 风险降级）✅ + STATUS 同步 6/1 ✅ |

## Git ↔ 目录映射

> check_worklog.py 用它来判断「你是谁」，从而检查对应目录的日志。

| Git用户名 | 日志目录 |
|-----------|----------|
| oldmanpushbike | 黎 |
| （待补充） | 董 |
| xiangbianpangde | 袁 |

## 图例
- ⚠️ 阻塞中（写明等谁/等什么）
- 🔀 涉及跨域接口，需协调
- ✅ 完成
