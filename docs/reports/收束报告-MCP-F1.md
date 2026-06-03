# 收束报告 — MCP F1（市场 + 安装）

> 收束节点：MCP 功能 v1 · 收束-1（F1） | 日期：2026-06-03 | 主导：袁（Claude Agent 协助）
> 范围：`feature/mcp/pr01-freeze-and-plan-cleanup` 上 MCP F1 批次（commit `3c0027c`..`f59a45a`）
> 模式：单人项目（袁 + Claude）——AI 广覆盖扫描 + 人审签核占位（待袁复核）
> 关联：[ADR-04](../../worklogs/decisions/0004-mcp-f1-landing-and-installer-seam.md) · [ADR-03](../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md) · [README-REVISION §9](../plan/后续升级计划/MCP接入/README-REVISION.md)

---

## 0. 批次概述

| 项 | 内容 |
|----|------|
| 功能点 | F1 市场（list/detail/templates）+ 安装（install/uninstall）+ 二次对账 + 安装探针 |
| 提交 | 6 commit（fix×1 / docs×2 / feat×3），均 Conventional Commits |
| 代码 | domain/mcp（5）+ repo 接口/实现 + models 4 表 + alembic 0006-0009 + 2 service + router 5 端点 + schemas + installer 端口/实现 + deps |
| 测试 | `tests/test_mcp.py` 19 用例 |

---

## 1. 阶段一：整理

| 检查项 | 结果 |
|--------|------|
| 未使用 import/函数/变量 | ✅ ruff `All checks passed`（全 MCP 代码） |
| 注释代码块 / 调试代码 | ✅ 无（grep print/console/TODO/FIXME 于 domain/mcp 无命中） |
| 硬编码密钥 | ✅ 无 |
| 孤儿模块 / 依赖黑洞 | ✅ 无（新模块均被 router/deps 引用） |
| worklog 齐全 | ✅ `worklogs/袁/2026-06-03_MCP-P1核心链路+二次对账.md` |
| 过时文档归档 | ✅ 无新增过时文档（原计划残留已于 P0 归档） |
| CLAUDE.md / STATUS / roadmap | ✅ 已更新（CLAUDE 路径修正 + STATUS 袁行/交接 + roadmap §十 P0.5/P1） |
| FILE_GRAPH 同步 | ✅ 无需改：新 `domain/mcp/`、`infrastructure/mcp/` 落入 FILE_GRAPH 既有 L1/L2 粗粒度归类 |
| 决策提升 ADR | ✅ ADR-04（二次对账落地口径 + 安装探针架构） |

**整理结论**：无熵增残留。

---

## 2. 阶段二：测试

### 自动化测试（SQLite + fakeredis）
- **全量**：`pytest` → **102 passed, 2 failed**（耗时 ~18s）
- **MCP 专项**：`tests/test_mcp.py` → **19/19 通过**，覆盖三路径（T-03）：
  - rules：args_hash 顺序无关/区分内容、version/batch 边界、install 配置按 transport 校验
  - market：仅列 published、q/tag/transport/official 过滤 + 分页、detail found/404
  - install：创建 ready、幂等（同 args_hash 返同一安装）、name 冲突 409、mcp 404、非法配置 422
  - uninstall：移除、404/跨 workspace、409 active 绑定守卫
  - 路由注册：5 端点装配

### 失败项分析（均与本批次无关）
| 失败 | 原因 | 归类 |
|------|------|------|
| `test_pi_agent_e2e::test_subprocess_lifecycle` | `FileNotFoundError` 拉起 pi-agent CLI（本机 Windows 未装） | 🟢 环境 |
| `test_pi_agent_e2e::test_factory_routing` | 同上，依赖 CLI | 🟢 环境 |

> 另：`test_selector::test_llm_failure_degrades_to_done`、`test_context_builder::test_group_delta_only_after_watermark` 在更大序集下偶发失败（本次未复现）。已确认为既有套件的**测试隔离/环境敏感**问题（context_builder 单跑/与 MCP 同跑均绿，仅全序失败——模块级 fakeredis 单例共享）。**非本批次引入**，记入技术债。

### 隔离性
MCP 19 用例每例独立 `db_session`（内存 SQLite），与 redis/watermark 无耦合；单跑、与 context_builder 同跑均全绿，无 flaky。

**测试结论**：本批次代码 100% 通过；2 失败为 Windows 无 CLI 的环境项，权威跑测在 Docker。

---

## 3. 阶段三：审计（AI 线 + 人线占位）

### 3.1 AI 审计线（全量扫描）

| 维度 | 检测 | 结果 |
|------|------|------|
| AR-01 5 层洋葱 | grep domain/mcp 的 sqlalchemy/fastapi/infrastructure import | ✅ 零依赖上层/框架/ORM |
| AR-01 L3 框架无关 | grep services 的 fastapi import | ✅ 无 |
| AR-02 只扩展 Adapter | 未另起运行时；`McpInstaller`/`attach_mcp` 走端口扩展 | ✅（attach_mcp 端口待 P2 实装） |
| CR-01/10/11 print/密钥/注释码 | grep 全 MCP 代码 | ✅ 无 |
| CR（ruff 全集） | `ruff check` 全 MCP 代码 | ✅ All checks passed |
| PR-02 分支命名 | `feature/mcp/pr01-freeze-and-plan-cleanup` | ✅ |
| PR-03 Conventional | 6 commit 全合规 | ✅ |
| PR-09 SPEC 同步 | 03-data-model/04-commands/README-REVISION 三处对账 | ✅ |
| AP-01 URL kebab+复数 | `/api/mcp/market`、`/installations` | ✅（market 为集合名） |
| AP-02 错误信封 | 沿用 `{detail}` | ⚠️ 已知 defer（D3/R9，全库一致，NB-02） |
| AP-05 URL 版本 | `/api/mcp`（无 v1） | ⚠️ 已知 defer（ADR-03） |
| T-03 三路径 | 19 用例覆盖正常/边界/异常 | ✅ |
| D-11 CLAUDE 路径 | `check_docs.py` 路径项全过 | ✅（仅剩 hooks 未装，环境项） |

**AI 审计结论：无 🔴 红线违规。** 2 项 🟡 为既有 defer（AP-02/AP-05），已立 ADR/backlog，非本批次新违规。

### 3.2 人审计线（袁签核 ✅ 2026-06-03）

- [x] AI 标记项复核：AP-02/AP-05 defer **接受**（ADR-03 + ADR-04 记录）
- [x] 业务逻辑：安装幂等键 `(workspace_id+mcp_id+args_hash)` + instance_name 唯一 **符合预期**
- [x] 设计意图：`workspace_id=session_id` stand-in **认可为合理过渡**（前向兼容真实 workspaces）
- [x] 主观质量：`McpInstaller` 端口 / 安装=校验语义 **清晰可接手**

> **袁签核结论：通过。** 收束-1（F1）AI 线 + 人线双线通过，**闭合**。

---

## 4. 阶段四：效果验证

### 契约回演（§2.6 PR-01 冻结草案）
| 端点 | 契约要点 | 实现 |
|------|---------|------|
| GET /api/mcp/market | 分页 + q/tag/transport/official 过滤，仅 published | ✅ |
| GET /api/mcp/market/templates | 官方模板（published & official） | ✅ |
| GET /api/mcp/market/{mcp_id} | 详情，404 | ✅ |
| POST /api/mcp/installations | 幂等安装，409 name 冲突，422 非法配置 | ✅ |
| DELETE /api/mcp/installations/{id} | 卸载，404/跨 ws，409 active 绑定 | ✅ |

### 用户故事回溯
F1 让「workspace 浏览 MCP 市场 → 安装到工作区」闭环在后端可走通（前端 P3）。方向对齐 PRD F1。**未偏离**。

### 可视化产出
本批次为后端 API，无 UI；端点行为由 19 单测覆盖。前端可视化验证留 P3（届时按「UI 改动要真浏览器验证」记忆项执行）。E2E（Playwright 5 Story）不在 F1 范围。

### 技术债盘点（新增，记入 STATUS）
| 问题 | 发现 | 优先级 | 预计 |
|------|------|--------|------|
| 既有套件测试隔离 flaky（fakeredis 模块单例 / selector LLM 环境敏感） | F1 收束 | 🟡 中 | 独立工单 |
| `agent_mcp_bindings` UNIQUE(agent,installation) 与软删 rebind 冲突 | F1 实现 | 🟡 中 | P2 绑定前解 |
| 安装为校验骨架（无真实可达性/进程探针） | F1 设计 | 🟢 低 | P2/P3 seam |
| AP-02 错误信封 / AP-05 版本 / workspaces·users 实体 / 全局鉴权 | 二次对账 | 🟢 低 | NB-02 |

---

## 5. 收束结论

| 阶段 | 结论 |
|------|------|
| 整理 | ✅ 无残留 |
| 测试 | ✅ 本批次 19/19；全量 2 失败为环境项 |
| 审计 | ✅ AI 线无红线；人线待袁签核 |
| 验证 | ✅ §2.6 契约回演通过，方向未偏 |

**收束-1（F1）：AI 线 + 人线双线通过，✅ 闭合（2026-06-03）。** 进入 P2（F2 Agent 绑定 + `attach_mcp`）。

### 关闭动作（已完成）
- [x] 袁完成人审签核（§3.2，通过）
- [x] Git tag `mcp-f1` 打于闭合提交
- [x] F1 + 收束并入 `main`（袁授予直接合并权）
- [x] 本报告 + ADR-04 已提交
