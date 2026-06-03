# 当前状态

> 最后更新: 2026-06-03
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | CLI 自动扫描 + Provider 矩阵 + Step 2 重设计 + OpenCode 集成 (9 bugs 修) | 无 | merge 39 commits ✅ + CLI PATH 扫描 ✅ + ProviderKeyResolver ✅ + Step 2 重设计 ✅ + OpenCode v1.15 集成 ✅ + PiAgentRuntime 修正 ✅ + Key 管理简化 ✅ + 工作目录 E2E ✅ + bug 修复 9 个 ✅ + OpenCode 对话待验证 |
| 董 | Phase 0 验收通过 + ADR-02 写入 + Phase 1 设计/实现完成（长驻 CLI + 拆 delta + 池） | 口吻传染独立工单 | CLI 多模型代理 ✅ + Phase 0 措辞修复 ✅ + Phase 0.5 V1-V5 验证 ✅ + 量化基线(互串 0%) ✅ + ADR-02 长驻 CLI 方案 ✅ + Phase 1 Step 1-4 实现 ✅ + 拆 delta ✅ + 22 单元用例 ✅ |
| 袁 | MCP 计划整理 + PR-01 端点冻结草案完成（路径校正 + `/api/mcp` 冻结草案落 04-commands §2.6 + 445 桩归档 + ADR-0003），**待 2 人 Review §2.6 后进 P1** | 无 | 全项目按模板重构 ✅ + 2026-05-29 目录二次整合 ✅ + skills 移回根 ✅ + 双图谱启用 ✅ + 图谱可视化离线化 ✅ + enums 影响分析 ✅ + dashboard 适配按人协作表 ✅ + src/frontend 代码内容分离 ✅ + 全栈运行验证 ✅ + 文档命名收敛 ✅ + dashboard 集成 ✅ + CODE_MAP.md 收归 docs/ ✅ + 远程 main 同步 5e34bea ✅ + 后续升级计划 v1.0 ✅ + roadmap §八 MVP 收尾冲刺 ✅ + STATUS 同步 6/1 ✅ + MCP 功能计划 v0.2 ✅ + MCP PRD v1.0 ✅ + roadmap §十 MCP v1 阶段表 ✅ + STATUS 同步 6/2 ✅ + MCP 接入计划可行性 review（12 问题清单）✅ + **MCP 接入计划修订版（2026-06-03）：README-REVISION.md 单一权威 + PRD V1.3.1 errata 4 项决策（表名/SDK/dry-run/前端）+ FS/SA/TA/MD/IC 5 份重写到 src/backend/app/ 真实栈 + 新增 MCP-UI-frontend V1.0（3 页+1 Tab+1 store+6 组件）+ 22 份 M-*/DEPRECATED.md 标记 + closure-verdict 双口径（计划空间🟢/代码空间🔴）+ end-to-end-trace 18 拍真实代码空间标注** ✅ + **MCP 计划整理 + PR-01 草案（2026-06-03）：核验修订版对真实代码树（5 层洋葱/llm runtime/alembic 0001-0005）属实 + 校正 §3 残留路径漂移（agentruntime→llm、api/v1→api/routers、application/mcp→services、虚构 BaseAgentRuntime→domain/llm/protocol.py::AgentRuntime）+ PR-01 端点冻结草案落 04-commands §2.6（8 端点）+ §三（4 WS 事件，type/payload 信封+request_id）+ ADR-0003（URL=/api/mcp、AP-05 暂缓）+ 原计划残留归档 docs/archive/DEPRECATED_MCP接入-原计划残留/（445+22+3 文件）+ FILE_GRAPH §5.3/5.6 同步** ✅ |

## ⏭️ 进行中交接

- **MCP 接入（代码开发待启动）**：计划已整理 + PR-01 端点冻结草案完成（2026-06-03，docs-only，commit `2025d42`，分支 `feature/mcp/pr01-freeze-and-plan-cleanup`，**未 push**）。
  - **下一会话从这里开始** → `docs/plan/开发清单_roadmap.md` §十「▶ 接手指引」（含落地权威三件套 + 关键约定 + P1 第一步）。
  - **前置红线**：`docs/specs/04-commands` §2.6（8 端点）+ §三（4 WS 事件）是 🔒 草案，**需 2 人 Review Approve（PR-01）后才能写代码**。
  - 关键约定速记：URL `/api/mcp/`（无 v1，ADR-0003）· 4 表追加进 `infrastructure/db/models.py` + alembic 0006 · `attach_mcp` 落 `domain/llm/protocol.py::AgentRuntime`。

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
