# 当前状态

> 最后更新: 2026-05-29
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | 前端 Agent 创建 3 步向导 + CLI 代理联调 bug 修复 + Docker 部署验证 | 无 | ClaudeAdapter 完整重写 ✅ + 文档治理 ✅ + Agent 创建向导 ✅ + CLI 代理联调 ✅ + nginx 反向代理 ✅ |
| 董 | 域2: CLI 多模型代理实现（cc-haha 分析 + 代理方案设计 + 代码实现） | 待端到端验证（需要真实 API Key） | ADR-01 ✅ + v4 PRD ✅ + adapter-cli-flow-analysis v1.3 ✅ + CLI 多模型代理方案设计 ✅ + proxy handler/router 实现 ✅ + ClaudeCodeRuntime 适配代理模式 ✅ |
| 袁 | chore/align-with-conventions PR 待合并（含目录二次整合 + 代码图谱）| 无 | 全项目按模板重构 ✅ + 2026-05-29 目录二次整合（src//docs/ + ~50 文件引用）✅ + skills 移回根 ✅ + 双图谱启用（gen_codegraph.py + CODE_MAP + AI/人视图，0 跨层违规）✅ |

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
