# 当前状态

> 最后更新: 2026-06-03
> 规则：**每次 push 或开始/结束一个任务时，更新你自己的那一行。**

| 我 | 正在做 | 阻塞？ | 这周完成了 |
|----|--------|--------|-----------|
| 黎 | CLI 自动扫描 + Provider 矩阵 + Step 2 重设计 + OpenCode 集成 (9 bugs 修) | 无 | merge 39 commits ✅ + CLI PATH 扫描 ✅ + ProviderKeyResolver ✅ + Step 2 重设计 ✅ + OpenCode v1.15 集成 ✅ + PiAgentRuntime 修正 ✅ + Key 管理简化 ✅ + 工作目录 E2E ✅ + bug 修复 9 个 ✅ + OpenCode 对话待验证 |
| 董 | Phase 0 验收通过 + ADR-02 写入 + Phase 1 设计/实现完成（长驻 CLI + 拆 delta + 池） | 口吻传染独立工单 | CLI 多模型代理 ✅ + Phase 0 措辞修复 ✅ + Phase 0.5 V1-V5 验证 ✅ + 量化基线(互串 0%) ✅ + ADR-02 长驻 CLI 方案 ✅ + Phase 1 Step 1-4 实现 ✅ + 拆 delta ✅ + 22 单元用例 ✅ |
| 袁 | MCP F1 + 收束-1 ✅ 闭合（双线签核）并入 main；启动 P2（Agent 绑定 + attach_mcp） | 无 | 全项目按模板重构 ✅ + 2026-05-29 目录二次整合 ✅ + skills 移回根 ✅ + 双图谱启用 ✅ + 图谱可视化离线化 ✅ + enums 影响分析 ✅ + dashboard 适配按人协作表 ✅ + src/frontend 代码内容分离 ✅ + 全栈运行验证 ✅ + 文档命名收敛 ✅ + dashboard 集成 ✅ + CODE_MAP.md 收归 docs/ ✅ + 远程 main 同步 5e34bea ✅ + 后续升级计划 v1.0 ✅ + roadmap §八 MVP 收尾冲刺 ✅ + STATUS 同步 6/1 ✅ + MCP 功能计划 v0.2 ✅ + MCP PRD v1.0 ✅ + roadmap §十 MCP v1 阶段表 ✅ + STATUS 同步 6/2 ✅ + MCP 接入计划可行性 review（12 问题清单）✅ + **MCP 接入计划修订版（2026-06-03）：README-REVISION.md 单一权威 + PRD V1.3.1 errata 4 项决策（表名/SDK/dry-run/前端）+ FS/SA/TA/MD/IC 5 份重写到 src/backend/app/ 真实栈 + 新增 MCP-UI-frontend V1.0（3 页+1 Tab+1 store+6 组件）+ 22 份 M-*/DEPRECATED.md 标记 + closure-verdict 双口径（计划空间🟢/代码空间🔴）+ end-to-end-trace 18 拍真实代码空间标注** ✅ + **MCP 计划整理 + PR-01 草案（2026-06-03）：核验修订版对真实代码树（5 层洋葱/llm runtime/alembic 0001-0005）属实 + 校正 §3 残留路径漂移（agentruntime→llm、api/v1→api/routers、application/mcp→services、虚构 BaseAgentRuntime→domain/llm/protocol.py::AgentRuntime）+ PR-01 端点冻结草案落 04-commands §2.6（8 端点）+ §三（4 WS 事件，type/payload 信封+request_id）+ ADR-0003（URL=/api/mcp、AP-05 暂缓）+ 原计划残留归档 docs/archive/DEPRECATED_MCP接入-原计划残留/（445+22+3 文件）+ FILE_GRAPH §5.3/5.6 同步** ✅ + **MCP P1 核心链路（2026-06-03，Reviewer Approve §2.6 后）：二次对账 schema↔代码审计 R1-R10（无 workspaces/users 表→裸 Uuid、零 JWT 强制→get_current_user 仅解析、trace_id 零设施→净新增、WS 信封不符、错误体 {detail} 非 AP-02、SQLite 强制可移植类型）+ 修 .gitignore 裸 backend/ 误伤源码树阻断 bug + domain/mcp 4 实体+rules+repo 接口 + models 追加 4 表 + alembic 0006-0009 + market/install 2 service + api/routers/mcp.py 3 端点(list/detail/install) + schemas/mcp.py + spec 三处对账横幅(03-data-model/04-commands/README-REVISION §9) + 12 单测绿(三路径)** ✅ |

## ⏭️ 进行中交接

- **MCP P1（核心链路已落地，未 push）**：分支 `feature/mcp/pr01-freeze-and-plan-cleanup`，未 commit/push（袁惯例：等确认）。
  - **已完成**：二次对账 R1-R10（README-REVISION §9）+ 数据层（domain/mcp 4 实体 + repo 接口/实现 + models 4 表 + alembic 0006-0009）+ market/install 2 service + `api/routers/mcp.py` 3 端点（list/detail/install）+ schemas/mcp.py + `get_current_user`（JWT 仅解析）+ 12 单测绿。
  - **落地口径**（二次对账后）：`workspace_id` 暂存 `session_id` 裸 Uuid 无 FK · `created_by/installed_by` 裸 Uuid 存 JWT sub · 可移植类型（JSON/String/BigInteger.with_variant）· 错误体沿用 `{detail}`（R9）。
  - **F1 端点面已齐**（5 端点）：market list/detail/templates + install/uninstall（19 单测绿）。
  - **安装探针**：`McpInstaller` 端口（L2）+ `LocalMcpInstaller`（L1）结构校验——stdio 需 command / 远程需合法 url，非法配置 → 422 拦截。真实可达性/进程拉起是 P2/P3 seam（已在实现 docstring 标注扩展点）。
  - **P1 剩余**：真实可达性/进程探针 · 收束 1 + ADR 0004 · `attach_mcp` 扩展点（P2）。
  - **本机环境**：tests 需 `pip install aiosqlite fakeredis pytest-cov anthropic`（已装）；权威跑测在 Docker。后端 95/98 通过（3 失败为环境无关：pi-agent CLI 未装 + selector LLM 兜底，非本次改动）。
  - ⚠️ **已修 `.gitignore` 阻断 bug**：裸 `backend/` 误伤 `src/backend/` 致新增后端文件全被忽略 → 锚定为 `/backend/`。push 前确认此修正在内。

## 🧾 技术债（收束盘点）

| 问题 | 发现 | 优先级 | 预计修复 |
|------|------|--------|---------|
| 既有套件测试隔离 flaky（`test_context_builder` 模块级 fakeredis 单例 / `test_selector` LLM 环境敏感）| MCP F1 收束-1 | 🟡 中 | 独立工单（非 MCP 引入）|
| `agent_mcp_bindings` UNIQUE(agent,installation) 与软删 rebind 冲突 | MCP F1 实现 | 🟡 中 | P2 绑定前（见 models.py NOTE）|
| 安装为结构校验骨架（无真实可达性/进程探针）| MCP F1 设计 | 🟢 低 | P2/P3（McpInstaller seam）|
| NB-02 defer：AP-02 错误信封统一 / AP-05 URL 版本 / workspaces·users 实体+FK / 全局 JWT 鉴权 | 二次对账 | 🟢 低 | 平台化阶段 |

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
