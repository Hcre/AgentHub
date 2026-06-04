# 当前状态

> 最后更新: 2026-06-03
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | CLI 自动扫描 + Provider 矩阵 + Step 2 重设计 + OpenCode 集成 (9 bugs 修) | 无 | merge 39 commits ✅ + CLI PATH 扫描 ✅ + ProviderKeyResolver ✅ + Step 2 重设计 ✅ + OpenCode v1.15 集成 ✅ + PiAgentRuntime 修正 ✅ + Key 管理简化 ✅ + 工作目录 E2E ✅ + bug 修复 9 个 ✅ + OpenCode 对话待验证 |
| 董 | 协调者+任务编排部分 | 无 | 群聊全栈实现 ✅ + CLI 多模型代理 ✅ + ADR-02 长驻 CLI ✅ + 前端群聊 ✅ + 记忆系统 B 方向设计 ✅ + B1 后端实现 ✅ + B2 详细设计 ✅ + Agent 创建全链路 6 处 bug 修复 + 9 个测试 ✅ + MCP save_memory 端到端打通 ✅ + 前端记忆面板 ✅ + 记忆分支合并 main ✅ |
| 袁 | MCP P2 核心：bind/unbind 端点 + 请求携带 attach（ADR-05）+ claude_code 注入 + rebind 修复 + 26 测试绿 | 无 | 全项目按模板重构 ✅ + 2026-05-29 目录二次整合 ✅ + skills 移回根 ✅ + 双图谱启用 ✅ + 图谱可视化离线化 ✅ + enums 影响分析 ✅ + dashboard 适配按人协作表 ✅ + src/frontend 代码内容分离 ✅ + 全栈运行验证 ✅ + 文档命名收敛 ✅ + dashboard 集成 ✅ + CODE_MAP.md 收归 docs/ ✅ + 远程 main 同步 5e34bea ✅ + 后续升级计划 v1.0 ✅ + roadmap §八 MVP 收尾冲刺 ✅ + STATUS 同步 6/1 ✅ + MCP 功能计划 v0.2 ✅ + MCP PRD v1.0 ✅ + roadmap §十 MCP v1 阶段表 ✅ + STATUS 同步 6/2 ✅ + MCP 接入计划可行性 review（12 问题清单）✅ + **MCP 接入计划修订版（2026-06-03）：README-REVISION.md 单一权威 + PRD V1.3.1 errata 4 项决策（表名/SDK/dry-run/前端）+ FS/SA/TA/MD/IC 5 份重写到 src/backend/app/ 真实栈 + 新增 MCP-UI-frontend V1.0（3 页+1 Tab+1 store+6 组件）+ 22 份 M-*/DEPRECATED.md 标记 + closure-verdict 双口径（计划空间🟢/代码空间🔴）+ end-to-end-trace 18 拍真实代码空间标注** ✅ + **MCP 计划整理 + PR-01 草案（2026-06-03）：核验修订版对真实代码树（5 层洋葱/llm runtime/alembic 0001-0005）属实 + 校正 §3 残留路径漂移（agentruntime→llm、api/v1→api/routers、application/mcp→services、虚构 BaseAgentRuntime→domain/llm/protocol.py::AgentRuntime）+ PR-01 端点冻结草案落 04-commands §2.6（8 端点）+ §三（4 WS 事件，type/payload 信封+request_id）+ ADR-0003（URL=/api/mcp、AP-05 暂缓）+ 原计划残留归档 docs/archive/DEPRECATED_MCP接入-原计划残留/（445+22+3 文件）+ FILE_GRAPH §5.3/5.6 同步** ✅ + **MCP P1 核心链路（2026-06-03，Reviewer Approve §2.6 后）：二次对账 schema↔代码审计 R1-R10（无 workspaces/users 表→裸 Uuid、零 JWT 强制→get_current_user 仅解析、trace_id 零设施→净新增、WS 信封不符、错误体 {detail} 非 AP-02、SQLite 强制可移植类型）+ 修 .gitignore 裸 backend/ 误伤源码树阻断 bug + domain/mcp 4 实体+rules+repo 接口 + models 追加 4 表 + alembic 0006-0009 + market/install 2 service + api/routers/mcp.py 3 端点(list/detail/install) + schemas/mcp.py + spec 三处对账横幅(03-data-model/04-commands/README-REVISION §9) + 12 单测绿(三路径)** ✅ |

## ⏭️ 进行中交接

- **MCP F1 已并入 main + 收束-1 闭合**（tag `mcp-f1`）：market+install 5 端点 + 安装探针 + ADR-04 + 收束报告。落地口径见 README-REVISION §9 + ADR-04。
- **MCP P2 核心已落地**（分支 `feature/mcp/p2-binding-attach`）：
  - **绑定**：`POST/DELETE /api/mcp/bindings` + `McpBindingService`（bind/unbind）+ binding repo；`agent_mcp_bindings` 改 status=active **部分唯一**（alembic 0010）→ 解绑后可 rebind。
  - **attach = 请求携带**（ADR-05）：`AgentRequest.mcp_servers` + `build_request_mcp_servers` + `ContextBuilder` 可选 `mcp_resolver` 注入（私聊/群聊）；claude_code runtime 扩展董 `_write_mcp_config` 合并记忆 server + 绑定 servers 写 `.mcp.json`。
  - **26 单测绿**（F1 18 + P2 8）；全量 110/112（2 失败 = pi-agent CLI 环境项）。
  - ⚠️ **运行时审计校正（2026-06-03）**：MCP 注入**仅 claude_code 可行**——opencode/pi_agent runtime 代码 0 处 MCP，连董记忆 MCP 也只 claude_code 生效。opencode 全局 config 写绑定跨 agent 串号；pi_agent CLI 无 MCP flag。**opencode/pi_agent MCP 移 NB-02**（opencode 需 per-workspace 项目级 config 隔离；pi_agent 需确认上游 CLI MCP 支持）。非 claude_code 的 agent 本期无 MCP（含记忆）。
  - **P2 剩余**：收束-2 · 工具级 tool_subset 过滤（P4）。
  - ⚠️ **`/api/mcp` 路径重叠**：董记忆 ASGI mount vs 本市场 router（现靠注册顺序消歧，P4 前裁）。

## 🧾 技术债（收束盘点）

| 问题 | 发现 | 优先级 | 预计修复 |
|------|------|--------|---------|
| 既有套件测试隔离 flaky（`test_context_builder` 模块级 fakeredis 单例 / `test_selector` LLM 环境敏感）| MCP F1 收束-1 | 🟡 中 | 独立工单（非 MCP 引入）|
| `agent_mcp_bindings` UNIQUE(agent,installation) 与软删 rebind 冲突 | MCP F1 实现 | 🟡 中 | P2 绑定前（见 models.py NOTE）|
| 安装为结构校验骨架（无真实可达性/进程探针）| MCP F1 设计 | 🟢 低 | P2/P3（McpInstaller seam）|
| NB-02 defer：AP-02 错误信封统一 / AP-05 URL 版本 / workspaces·users 实体+FK / 全局 JWT 鉴权 | 二次对账 | 🟢 低 | 平台化阶段 |
| ⚠️ `/api/mcp` 路径重叠：董记忆 `app.mount("/api/mcp", mcp_memory ASGI)` 与本市场 router `prefix=/api/mcp` 同基路径（现靠注册顺序消歧）| F1↔记忆 merge | 🟡 中 | P2 前裁路径划分 |
| MCP 注入 claude_code-only（R11）：opencode/pi_agent runtime 0 处 MCP，非 claude_code agent 无 MCP（含记忆）| P2 运行时审计 | 🟡 中 | NB-02（opencode per-workspace config / pi_agent 待确认上游） |

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
